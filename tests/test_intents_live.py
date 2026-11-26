"""Acceptance emails against the real local model (opt-in: OLLAMA_LIVE=1 uv run pytest tests/test_intents_live.py -v).

Email text and expected results are kept apart: only `subject` and `body` are sent to the model.
"""

import os

import pytest

from core import DEFAULT_MODEL, classify

CASES = {
    "AC1-nouvelle-location": (
        "Mariage à Deshaies",
        "Bonjour, je cherche 40 chaises pour un mariage à Deshaies. Quel serait votre tarif ?",
    ),
    "AC2-D402-modification": (
        "Devis D-402 : changement de date",
        (
            "Bonjour, pour le devis D-402 déjà signé, pouvez-vous décaler la livraison des chapiteaux du 5 au 6 décembre ? "
            "Le reste ne change pas."
        ),
    ),
    "AC3-D402-horaire": (
        "Devis D-402 : livraison",
        "Bonjour, pour le devis D-402 déjà signé, à quelle heure est prévue la livraison des chapiteaux le 5 décembre ?",
    ),
    "AC4-retrait-partiel": (
        "Réservation de samedi",
        "Pour notre réservation confirmée, retirez deux tables et gardez le reste.",
    ),
    "AC4-annulation-totale": ("Réservation de samedi", "Nous annulons toute notre réservation de samedi."),
    "AC5-fournisseur": (
        "Promotion sur nos barnums",
        (
            "Bonjour, notre société vend des barnums et des tables pliantes. Profitez de -15 % sur nos prix de gros "
            "jusqu’à fin décembre."
        ),
    ),
    "AC5-panne": (
        "Sono en panne",
        "Bonjour, la sono livrée hier pour notre soirée ne s’allume plus. Que pouvons-nous faire ?",
    ),
}
EXPECTED = {
    "AC1-nouvelle-location": "nouvelle_location",
    "AC2-D402-modification": "modification_location",
    "AC3-D402-horaire": "autre",
    "AC4-retrait-partiel": "modification_location",
    "AC4-annulation-totale": "autre",
    "AC5-fournisseur": "autre",
    "AC5-panne": "autre",
}

pytestmark = pytest.mark.skipif(os.getenv("OLLAMA_LIVE") != "1", reason="real model: set OLLAMA_LIVE=1")


@pytest.mark.parametrize("case", list(CASES))
def test_acceptance_email(case: str) -> None:
    """Expected category; a valid answer has already passed parse_verdict (contract + exact quote)."""
    subject, body = CASES[case]
    verdict = classify(subject, body, os.getenv("OLLAMA_MODEL", DEFAULT_MODEL))
    assert verdict.category == EXPECTED[case]
    assert (verdict.quote in body) and bool(verdict.quote) == (EXPECTED[case] != "autre")
    if case == "AC2-D402-modification":
        assert "5 au 6 décembre" in verdict.quote
