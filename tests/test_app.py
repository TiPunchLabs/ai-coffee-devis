"""Work-queue rendering and counters for the three intentions (model mocked, no network)."""

import pytest

import app
from core import AnalysisError, Verdict
from live_inbox import LiveMail

D402_BODY = (
    "Bonjour, pour le devis D-402 déjà signé, pouvez-vous décaler la livraison des chapiteaux "
    "du 5 au 6 décembre ? Le reste ne change pas."
)
D402_QUOTE = "pouvez-vous décaler la livraison des chapiteaux du 5 au 6 décembre ?"
MAILS = {
    "new": (
        "Mariage à Deshaies",
        "Bonjour, je cherche 40 chaises pour un mariage à Deshaies. Quel serait votre tarif ?",
    ),
    "d402": ("Devis D-402 : changement de date", D402_BODY),
    "other": ("Livraison D-402", "Bonjour, à quelle heure est prévue la livraison des chapiteaux le 5 décembre ?"),
}
VERDICTS = {
    "new": Verdict("nouvelle_location", "Quel serait votre tarif ?"),
    "d402": Verdict("modification_location", D402_QUOTE),
    "other": Verdict("autre", ""),
}


@pytest.fixture
def inbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three retrieved messages and a mocked classifier keyed by subject."""
    monkeypatch.setattr(app.MAILBOX, "messages", {})
    for minute, (mid, (subject, body)) in enumerate(MAILS.items()):
        app.MAILBOX.messages[mid] = LiveMail(mid, f"2026-11-26T18:0{minute}:00Z", subject, body)
    by_subject = {subject: VERDICTS[mid] for mid, (subject, _) in MAILS.items()}
    monkeypatch.setattr(app, "classify", lambda subject, *args: by_subject[subject])


def analyze(mid: str, verdicts: dict) -> tuple[str, dict, str, str]:
    """Run the live « Analyser ce message » callback."""
    return app.analyze_live(mid, "m", app.PROMPT, app.USER_TEMPLATE, verdicts)


def test_d402_is_a_modification_to_process(inbox: None) -> None:
    """AC2: badge, quote and next step agree; listed as « à traiter », not as a new inquiry."""
    status, _, queue, detail = analyze("d402", {})
    assert "Modification de location" in status
    assert "◆ Modification de location" in detail and D402_QUOTE in detail
    assert "Vérifier si la modification est possible et répondre au client." in detail
    assert "Rien de nouveau" not in detail and "Pas une demande" not in detail
    assert "1 à traiter" in queue and "0 nouvelle(s) demande(s) de location" in queue
    original = detail.split("Courriel d’origine", 1)[1]
    assert "<mark class='q-quote'>" + D402_QUOTE + "</mark>" in original  # original text kept, quote marked


def test_counters_with_three_intentions_and_reanalysis(inbox: None) -> None:
    """AC7: 2 to process, 1 new inquiry; re-analysing a message never counts it twice."""
    verdicts: dict = {}
    for mid in MAILS:
        _, verdicts, queue, _ = analyze(mid, verdicts)
    assert "2 à traiter" in queue and "1 nouvelle(s) demande(s) de location" in queue
    for _ in range(3):
        _, verdicts, queue, _ = analyze("new", verdicts)
    assert "2 à traiter" in queue and "1 nouvelle(s) demande(s) de location" in queue
    other = app.show_message("other", verdicts)
    assert "Hors périmètre" in other and "Si le courriel pose une question, y répondre normalement." in other


def test_analysis_error_is_not_counted_as_classified(inbox: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """AC6 in the UI: a rejected answer shows « Analyse à vérifier », distinct from « Hors périmètre »."""

    def broken(*args: object) -> Verdict:
        raise AnalysisError("catégorie inconnue renvoyée par le modèle : 'location'")

    monkeypatch.setattr(app, "classify", broken)
    status, _, queue, detail = analyze("d402", {})
    assert "Analyse à vérifier" in status and "▲ Analyse à vérifier" in detail
    assert "Hors périmètre" not in detail
    assert "0 à traiter" in queue and "1 à vérifier" in queue


def test_stale_two_field_result_is_not_reused(inbox: None) -> None:
    """An old demande=false result cannot hide a modification: the message shows « Non analysé »."""
    old = {"d402": {"state": "none", "quote": ""}}
    assert "Non analysé" in app.show_message("d402", old)
    assert "à traiter" not in app.live_queue(old, "d402")


def test_prepared_score_counts_only_new_rentals() -> None:
    """A modification is « à traiter » but neither a found request nor a false alarm."""
    board = {"results": {}, "keyword": False, "revealed": True, "progress": None}
    board["results"]["08"] = app.outcome_from(Verdict("modification_location", "le gardien ouvrira le portail"))
    board["results"]["02"] = app.outcome_from(Verdict("nouvelle_location", "40 chaises"))
    header = app.prepared_header(board)
    assert "2 à traiter" in header and "1 nouvelle(s) demande(s) de location" in header
    assert app.check_mark("08", board["results"]["08"]) == "Modification de location (hors score)"
    assert app.check_mark("02", board["results"]["02"]) == "✓ Bonne détection"
