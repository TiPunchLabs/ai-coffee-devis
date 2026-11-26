"""Read-only AgentMail connector for the dedicated AI Coffee inbox.

Only three GET operations are used: get inbox, list messages, get message.
The API key stays in this process; it is never displayed nor logged.
"""

from __future__ import annotations

import html
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

import httpx

API_BASE = os.getenv("AGENTMAIL_BASE_URL", "https://api.agentmail.to/v0")
PAGE_LIMIT = 50
MAX_PAGES = 5
TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class MailboxError(Exception):
    """Failure with a short French message and a recovery action for the presenter."""


@dataclass(frozen=True)
class LiveMail:
    message_id: str
    timestamp: str
    subject: str
    body: str  # empty when no readable text could be extracted

    @property
    def usable(self) -> bool:
        """True when the body contains readable text to classify."""
        return bool(self.body.strip())


@dataclass(frozen=True)
class Config:
    api_key: str
    inbox_id: str


def read_config() -> Config:
    """Read credentials from the environment (exported by .envrc via direnv + pass)."""
    api_key = os.getenv("AGENTMAIL_API_KEY", "").strip()
    inbox_id = os.getenv("AGENTMAIL_INBOX_ID", "").strip()
    missing = [n for n, v in (("AGENTMAIL_API_KEY", api_key), ("AGENTMAIL_INBOX_ID", inbox_id)) if not v]
    if missing:
        raise MailboxError(
            f"Configuration AgentMail absente ({', '.join(missing)}). Vérifie `pass agentmail/ai-coffee-api-key` "
            "et `pass agentmail/ai-coffee-inbox-id`, lance `direnv allow` dans le projet, puis redémarre "
            "l’application depuis ce terminal. L’onglet « Démo préparée » reste utilisable."
        )
    return Config(api_key, inbox_id)


def html_to_text(markup: str) -> str:
    """Turn an HTML body into plain readable text without rendering anything."""
    markup = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n\n", text)).strip()


def readable_body(message: dict) -> str:
    """Pick the full readable body: new content first, then plain text, then HTML converted."""
    for field in ("extracted_text", "text"):
        value = message.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for field in ("extracted_html", "html"):
        value = message.get(field)
        if isinstance(value, str) and value.strip():
            return html_to_text(value)
    return ""


class Mailbox:
    """Keeps every retrieved message once, keyed by AgentMail's message_id."""

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self._transport = transport
        self._lock = threading.Lock()
        self.messages: dict[str, LiveMail] = {}
        self.verified_address: str | None = None

    def _get(self, client: httpx.Client, path: str, params: dict | None = None) -> dict:
        """Perform one GET and map failures to presenter-friendly errors."""
        try:
            response = client.get(path, params=params)
        except httpx.TimeoutException as err:
            raise MailboxError(
                "AgentMail ne répond pas (délai dépassé). Vérifie le Wi-Fi puis réessaie, "
                "ou reviens à l’onglet « Démo préparée »."
            ) from err
        except httpx.TransportError as err:
            raise MailboxError(
                "Pas d’accès Internet vers AgentMail. Vérifie le réseau puis réessaie, "
                "ou reviens à l’onglet « Démo préparée »."
            ) from err
        if response.status_code in (401, 403):
            raise MailboxError(
                "Clé AgentMail refusée. Vérifie l’entrée `pass agentmail/ai-coffee-api-key` "
                "(clé révoquée, mal copiée, ou sans droit de lecture sur cette boîte)."
            )
        if response.status_code == 404:
            raise MailboxError(
                "Boîte AgentMail introuvable pour cette clé. Vérifie `AGENTMAIL_INBOX_ID` "
                "(`pass agentmail/ai-coffee-inbox-id`) : c’est l’adresse complète, ex. ai-coffee@agentmail.to."
            )
        if response.status_code == 429:
            raise MailboxError("AgentMail limite les requêtes. Attends quelques secondes et réessaie.")
        if response.status_code >= 400:
            raise MailboxError(f"AgentMail indisponible (HTTP {response.status_code}). Réessaie dans un instant.")
        try:
            data = response.json()
        except ValueError as err:
            raise MailboxError("Réponse AgentMail illisible. Réessaie dans un instant.") from err
        if not isinstance(data, dict):
            raise MailboxError("Réponse AgentMail inattendue. Réessaie dans un instant.")
        return data

    def fetch(self) -> tuple[int, str]:
        """Retrieve new inbound messages. Return (new_count, French status)."""
        config = read_config()
        inbox = quote(config.inbox_id, safe="@")
        headers = {"Authorization": f"Bearer {config.api_key}", "Accept": "application/json"}
        with (
            self._lock,
            httpx.Client(
                base_url=API_BASE, headers=headers, timeout=TIMEOUT, transport=self._transport, follow_redirects=False
            ) as client,
        ):
            info = self._get(client, f"/inboxes/{inbox}")
            self.verified_address = str(info.get("email") or info.get("inbox_id") or config.inbox_id)
            items: list[dict] = []
            token: str | None = None
            for _ in range(MAX_PAGES):
                params: dict = {"limit": PAGE_LIMIT}
                if token:
                    params["page_token"] = token
                page = self._get(client, f"/inboxes/{inbox}/messages", params)
                batch = page.get("messages")
                if not isinstance(batch, list):
                    raise MailboxError("Réponse AgentMail inattendue (liste absente). Réessaie.")
                items.extend(m for m in batch if isinstance(m, dict))
                token = page.get("next_page_token")
                if not token:
                    break
            inbound = [
                m for m in items if "sent" not in (m.get("labels") or []) and isinstance(m.get("message_id"), str)
            ]
            if not inbound:
                return (
                    0,
                    "Boîte vide : aucun message reçu pour l’instant. Invite la salle à écrire, puis relève à nouveau.",
                )
            new = [m for m in inbound if m["message_id"] not in self.messages]
            if not new:
                return 0, f"Aucun nouveau message ({len(self.messages)} déjà relevé(s)). Réessaie dans 20 secondes."
            for item in new:
                full = self._get(client, f"/inboxes/{inbox}/messages/{quote(item['message_id'], safe='')}")
                self.messages[item["message_id"]] = LiveMail(
                    message_id=item["message_id"],
                    timestamp=str(full.get("timestamp") or item.get("timestamp") or ""),
                    subject=str(full.get("subject") or item.get("subject") or "(sans objet)").strip(),
                    body=readable_body(full),
                )
        unusable = sum(1 for m in new if not self.messages[m["message_id"]].usable)
        status = f"{len(new)} nouveau(x) message(s) relevé(s)."
        if unusable:
            status += f" {unusable} sans texte lisible (pièce jointe ou image seule) : demande un message en texte."
        return len(new), status

    def choices(self) -> list[tuple[str, str]]:
        """Dropdown entries, newest first. Labels show local time and subject, never the sender."""
        ordered = sorted(self.messages.values(), key=lambda m: m.timestamp, reverse=True)
        return [(f"{local_time(m.timestamp)} · {m.subject[:80]}", m.message_id) for m in ordered]


def local_time(timestamp: str) -> str:
    """Format an ISO timestamp as HH:MM in the laptop's time zone."""
    try:
        return datetime.fromisoformat(timestamp).astimezone().strftime("%H:%M")
    except ValueError:
        return "--:--"


def check() -> int:
    """Connection check for docs/AGENTMAIL.md: read-only, never prints the key."""
    try:
        config = read_config()
        print(f"Configuration lue : AGENTMAIL_INBOX_ID={config.inbox_id} · AGENTMAIL_API_KEY présente (masquée)")
        box = Mailbox()
        count, status = box.fetch()
    except MailboxError as err:
        print(f"ÉCHEC : {err}")
        return 1
    print(f"CONNEXION OK : boîte confirmée par AgentMail = {box.verified_address}")
    print(f"Messages reçus lisibles par l’application : {count}. {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
