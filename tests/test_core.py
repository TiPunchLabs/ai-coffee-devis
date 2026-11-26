"""Corpus, keyword baseline, quote validation and classifier error handling."""

import json

import httpx
import pytest
from openai import OpenAI

import core
from core import (
    EXPECTED,
    AnalysisError,
    PromptError,
    ServiceError,
    classify,
    keyword_matches,
    load_corpus,
    locate_quote,
    score,
)


def test_corpus_has_twenty_ids_with_leading_zeros() -> None:
    """The corpus keeps its 20 identifiers as strings."""
    assert [m.id for m in load_corpus()] == [f"{i:02d}" for i in range(1, 21)]


def test_keyword_baseline_and_score() -> None:
    """Whole-word « devis » yields 03, 07, 12, 18: 1 found, 3 false alarms, 3 missed."""
    ids = {m.id for m in keyword_matches(load_corpus())}
    assert ids == {"03", "07", "12", "18"}
    s = score(ids)
    assert (len(s["found"]), len(s["false_alarms"]), len(s["missed"])) == (1, 3, 3)
    assert EXPECTED == {"02", "07", "13", "17"}


def test_locate_quote_tolerates_apostrophes_but_rejects_inventions() -> None:
    """Quotes must appear contiguously in the email."""
    body = "Pouvez-vous nous faire un devis pour deux chapiteaux ?"
    assert locate_quote("« faire un devis »", "", body) == "faire un devis"
    assert locate_quote("Deux chapiteaux et leur montage", "", body) is None
    assert locate_quote("l'événementiel", "", "les métiers de l’événementiel") == "l’événementiel"
    assert locate_quote("", "", body) is None


def fake_ollama(monkeypatch: pytest.MonkeyPatch, status: int, content: str, seen: list) -> None:
    """Serve a canned answer from Ollama's OpenAI-compatible API and record each request body."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        seen.append(json.loads(request.content))
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "model not found"}})
        message = {"role": "assistant", "content": content}
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            },
        )

    client = OpenAI(
        base_url="http://ollama.test/v1",
        api_key="ollama",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(core, "get_client", lambda: client)


def test_classify_sends_only_subject_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """No identifier or answer key reaches the model; settings match the demo; quote returned verbatim."""
    seen: list = []
    fake_ollama(monkeypatch, 200, json.dumps({"demande": True, "citation": "40 chaises"}), seen)
    verdict = classify("Notre fête", "Il nous faudrait 40 chaises samedi.", "m")
    assert verdict.is_request and verdict.quote == "40 chaises"
    sent = seen[0]
    user = json.loads(sent["messages"][1]["content"])
    assert set(user) == {"objet", "message"}
    assert "02" not in json.dumps(sent["messages"])
    assert (sent["temperature"], sent["reasoning_effort"], sent["keep_alive"]) == (0, "none", "30m")
    assert sent["response_format"]["json_schema"]["schema"] == core.SCHEMA


def test_classify_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown model and Ollama down stop the run; bad output or invented quote need review."""
    fake_ollama(monkeypatch, 404, "", [])
    with pytest.raises(ServiceError, match="introuvable"):
        classify("a", "b", "inconnu:1b")
    fake_ollama(monkeypatch, 500, "", [])
    with pytest.raises(ServiceError, match="HTTP 500"):
        classify("a", "b", "m")
    fake_ollama(monkeypatch, 200, "pas du json", [])
    with pytest.raises(AnalysisError, match="illisible"):
        classify("a", "b", "m")
    fake_ollama(monkeypatch, 200, json.dumps({"demande": True, "citation": "inventé"}), [])
    with pytest.raises(AnalysisError, match="citation"):
        classify("a", "b", "m")

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    unreachable = OpenAI(
        base_url="http://ollama.test/v1",
        api_key="ollama",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(down)),
    )
    monkeypatch.setattr(core, "get_client", lambda: unreachable)
    with pytest.raises(ServiceError, match="Ollama ne répond pas"):
        classify("a", "b", "m")


def test_default_prompts_send_the_same_user_message_as_before(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default template renders exactly the historical JSON payload, even with tricky content."""
    seen: list = []
    fake_ollama(monkeypatch, 200, json.dumps({"demande": False, "citation": ""}), seen)
    subject, body = 'Objet {message} "x"', 'Corps {objet} {id} \\ "q"\nligne é' * 400
    classify(subject, body, "m")
    expected = json.dumps({"objet": subject, "message": body[: core.BODY_MAX_CHARS]}, ensure_ascii=False)
    assert seen[0]["messages"][0]["content"] == core.PROMPT
    assert seen[0]["messages"][1]["content"] == expected


def test_custom_prompts_are_sent_and_only_subject_and_body_are_filled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Edited prompts reach the model; only {objet} and {message} are replaced, once."""
    seen: list = []
    fake_ollama(monkeypatch, 200, json.dumps({"demande": False, "citation": ""}), seen)
    classify("Fête", "Texte avec {objet}", "m", system_prompt="Consigne test", user_template="O={objet} M={message}")
    assert seen[0]["messages"][0]["content"] == "Consigne test"
    assert seen[0]["messages"][1]["content"] == 'O="Fête" M="Texte avec {objet}"'


@pytest.mark.parametrize(
    ("system_prompt", "template", "expected"),
    [
        ("   ", core.USER_TEMPLATE, "prompt système est vide"),
        ("Consigne", "Objet : {objet}", "doit contenir {message}"),
        ("Consigne", "{id} {message}", "non autorisée"),
        ("Consigne", "{message} {corrige}", "non autorisée"),
    ],
)
def test_unusable_prompts_never_reach_the_model(
    monkeypatch: pytest.MonkeyPatch, system_prompt: str, template: str, expected: str
) -> None:
    """Empty system prompt, missing {message} or unknown placeholder: refused before any HTTP call."""
    seen: list = []
    fake_ollama(monkeypatch, 200, json.dumps({"demande": True, "citation": "x"}), seen)
    with pytest.raises(PromptError, match=expected):
        classify("a", "b", "m", system_prompt=system_prompt, user_template=template)
    assert seen == []
