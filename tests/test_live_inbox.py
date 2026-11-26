"""AgentMail connector against simulated API responses (no network)."""

import httpx
import pytest

from live_inbox import Mailbox, MailboxError, readable_body

INBOX = "ai-coffee-test@agentmail.to"


@pytest.fixture(autouse=True)
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fictional credentials."""
    monkeypatch.setenv("AGENTMAIL_API_KEY", "am_fake")
    monkeypatch.setenv("AGENTMAIL_INBOX_ID", INBOX)


def item(mid: str, ts: str, labels: list[str] | None = None) -> dict:
    """A list-messages entry (metadata and preview only)."""
    return {
        "message_id": mid,
        "timestamp": ts,
        "labels": labels or ["received", "unread"],
        "from": "Secret Sender <secret@example.com>",
        "subject": f"Objet {mid}",
        "preview": "aperçu…",
    }


class FakeApi:
    """Read-only AgentMail simulation with two pages and a call log."""

    def __init__(self, items: list[dict], bodies: dict[str, dict], status: int = 200) -> None:
        self.items, self.bodies, self.status, self.calls = items, bodies, status, []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer am_fake"
        self.calls.append(request.url.path)
        if self.status != 200:
            return httpx.Response(self.status, json={"name": "Error", "message": "x"})
        path = request.url.path
        if path == f"/v0/inboxes/{INBOX}":
            return httpx.Response(200, json={"inbox_id": INBOX, "email": INBOX})
        if path == f"/v0/inboxes/{INBOX}/messages":
            token = request.url.params.get("page_token")
            half = len(self.items) // 2 or len(self.items)
            if token == "p2":
                return httpx.Response(200, json={"count": 1, "messages": self.items[half:]})
            page = {"count": half, "messages": self.items[:half]}
            if half < len(self.items):
                page["next_page_token"] = "p2"
            return httpx.Response(200, json=page)
        mid = path.rsplit("/", 1)[1]
        return httpx.Response(
            200,
            json={
                "message_id": mid,
                "subject": f"Objet {mid}",
                "from": "secret@example.com",
                **self.bodies.get(mid, {}),
            },
        )


def box(api: FakeApi) -> Mailbox:
    """Mailbox wired to the simulation."""
    return Mailbox(transport=httpx.MockTransport(api))


def test_pagination_dedup_and_body() -> None:
    """Two pages are read, sent mail skipped, full text used, and repeats deduplicated."""
    items = [
        item("a", "2026-11-26T22:01:00Z"),
        item("b", "2026-11-26T22:02:00Z"),
        item("s", "2026-11-26T22:03:00Z", ["sent"]),
    ]
    api = FakeApi(items, {"a": {"text": "Bonjour, 40 chaises samedi ?"}, "b": {"extracted_text": "Corps B"}})
    mb = box(api)
    assert mb.fetch()[0] == 2
    assert mb.messages["a"].body == "Bonjour, 40 chaises samedi ?"
    assert mb.verified_address == INBOX
    count, status = mb.fetch()
    assert count == 0 and "Aucun nouveau message" in status
    assert len(mb.messages) == 2 and {v for _, v in mb.choices()} == {"a", "b"}
    assert not any("secret" in label for label, _ in mb.choices())
    assert "/v0/inboxes/ai-coffee-test@agentmail.to/messages/s" not in api.calls


def test_empty_inbox() -> None:
    """An empty inbox is reported as such."""
    assert "Boîte vide" in box(FakeApi([], {})).fetch()[1]


def test_unusable_body() -> None:
    """A message without any text is kept but flagged."""
    mb = box(FakeApi([item("x", "2026-11-26T22:00:00Z")], {"x": {}}))
    assert "sans texte lisible" in mb.fetch()[1]
    assert not mb.messages["x"].usable


@pytest.mark.parametrize(
    ("status", "expected"),
    [(401, "Clé AgentMail refusée"), (403, "Clé AgentMail refusée"), (404, "introuvable"), (500, "indisponible")],
)
def test_http_errors(status: int, expected: str) -> None:
    """Rejected key, wrong inbox and server errors give distinct messages."""
    with pytest.raises(MailboxError, match=expected):
        box(FakeApi([], {}, status)).fetch()


def test_network_failure() -> None:
    """A network failure is reported without crashing."""

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(MailboxError, match="Pas d’accès Internet"):
        Mailbox(transport=httpx.MockTransport(fail)).fetch()


def test_missing_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing credentials name the variable, never a value."""
    monkeypatch.delenv("AGENTMAIL_API_KEY")
    with pytest.raises(MailboxError, match="AGENTMAIL_API_KEY"):
        Mailbox().fetch()


def test_html_body_is_plain_text() -> None:
    """HTML bodies become plain text; scripts are dropped."""
    body = readable_body({"html": "<p>Bonjour</p><script>alert(1)</script><p>40 chaises &amp; tables</p>"})
    assert "<" not in body and "alert" not in body and "40 chaises & tables" in body
