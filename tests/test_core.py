"""Corpus, keyword baseline, quote validation and classifier error handling."""

import json

import httpx
import pytest

import core
from core import EXPECTED, AnalysisError, ServiceError, classify, keyword_matches, load_corpus, locate_quote, score


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
    """Replace httpx.post with a canned Ollama answer and record the payload."""

    def post(url: str, json: dict, timeout: float) -> httpx.Response:
        seen.append(json)
        body = {"message": {"content": content}} if status == 200 else {"error": "model not found"}
        return httpx.Response(status, json=body)

    monkeypatch.setattr(core.httpx, "post", post)


def test_classify_sends_only_subject_and_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """No identifier or answer key reaches the model; a valid quote is returned verbatim."""
    seen: list = []
    fake_ollama(monkeypatch, 200, json.dumps({"demande": True, "citation": "40 chaises"}), seen)
    verdict = classify("Notre fête", "Il nous faudrait 40 chaises samedi.", "m")
    assert verdict.is_request and verdict.quote == "40 chaises"
    user = json.loads(seen[0]["messages"][1]["content"])
    assert set(user) == {"objet", "message"}
    assert "02" not in json.dumps(seen[0]["messages"])


def test_classify_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown model and Ollama down stop the run; bad output or invented quote need review."""
    fake_ollama(monkeypatch, 404, "", [])
    with pytest.raises(ServiceError, match="introuvable"):
        classify("a", "b", "inconnu:1b")
    fake_ollama(monkeypatch, 200, "pas du json", [])
    with pytest.raises(AnalysisError, match="illisible"):
        classify("a", "b", "m")
    fake_ollama(monkeypatch, 200, json.dumps({"demande": True, "citation": "inventé"}), [])
    with pytest.raises(AnalysisError, match="citation"):
        classify("a", "b", "m")

    def down(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(core.httpx, "post", down)
    with pytest.raises(ServiceError, match="Ollama ne répond pas"):
        classify("a", "b", "m")
