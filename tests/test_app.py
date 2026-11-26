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


def run_batch(verdicts: dict, **prompts: str) -> list[tuple[str, dict, str, str]]:
    """All frames of the live « Analyser les messages non analysés » callback."""
    system = prompts.get("system", app.PROMPT)
    template = prompts.get("template", app.USER_TEMPLATE)
    return list(app.analyze_all_live("m", system, template, verdicts, "d402"))


def test_batch_analyses_every_pending_message_once(inbox: None) -> None:
    """Three intentions in one click; a message without text is skipped; a second click changes nothing."""
    app.MAILBOX.messages["img"] = LiveMail("img", "2026-11-26T18:09:00Z", "Photo", "")
    frames = run_batch({})
    status, verdicts, queue, detail = frames[-1]
    assert status.startswith("✅ **3 message(s) analysé(s)**")
    assert "2 à traiter, dont 1 nouvelle(s) demande(s) de location · 1 hors périmètre" in status
    assert "1 sans texte lisible, ignoré(s)" in status
    assert "2 à traiter" in queue and "1 nouvelle(s) demande(s) de location" in queue
    assert "◆ Modification de location" in detail and D402_QUOTE in detail  # selected message refreshed
    assert [f[0] for f in frames[1:-1]] == [f"⏳ {i}/3 message(s) analysé(s) · 0 s" for i in (1, 2, 3)]
    again = run_batch(verdicts)
    assert len(again) == 1 and again[0][0].startswith("Tous les messages relevés sont déjà analysés.")
    assert "2 à traiter" in again[0][2] and "1 nouvelle(s) demande(s) de location" in again[0][2]


def test_batch_reanalyses_stale_results_only(inbox: None) -> None:
    """Old-format results count as « Non analysé »; current results are kept as they are."""
    _, verdicts, _, _ = analyze("new", {})
    verdicts["d402"] = {"state": "none", "quote": ""}
    status = run_batch(verdicts)[-1][0]
    assert status.startswith("✅ **2 message(s) analysé(s)**")


def test_batch_stops_on_service_error_and_keeps_results(inbox: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ollama down after the first message: run interrupted, first result kept, others still pending."""
    calls: list[str] = []

    def flaky(subject: str, *args: object) -> Verdict:
        calls.append(subject)
        if len(calls) > 1:
            raise app.ServiceError("Ollama ne répond pas sur 127.0.0.1:11434.")
        return VERDICTS["other"]

    monkeypatch.setattr(app, "classify", flaky)
    status, verdicts, queue, _ = run_batch({})[-1]
    assert status.startswith("⛔ **Analyse interrompue** (1/3 traités)")
    assert len(verdicts) == 1 and "Non analysé" in queue


def test_batch_refuses_unusable_prompts_without_calling_the_model(inbox: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prompt checked once, before any message is sent."""
    monkeypatch.setattr(app, "classify", lambda *args: pytest.fail("model called"))
    frames = run_batch({}, template="{id} {message}")
    assert len(frames) == 1 and "Analyse impossible" in frames[0][0]


def test_batch_without_retrieved_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing retrieved yet: ask to fetch first."""
    monkeypatch.setattr(app.MAILBOX, "messages", {})
    assert run_batch({})[0][0].startswith("Aucun message relevé.")


def test_batch_stop_is_cooperative_and_keeps_screen_and_state_in_sync(inbox: None) -> None:
    """« Arrêter » after the first message: the run ends cleanly and shows exactly the stored results."""
    frames = app.analyze_all_live("m", app.PROMPT, app.USER_TEMPLATE, {}, "d402")
    next(frames)  # « Analyse de 3 message(s)… »
    next(frames)  # first message done
    assert app.stop_live_analysis().startswith("⏳ Arrêt demandé")
    status, verdicts, queue, _ = next(frames)
    assert status.endswith("(1/3 traités)") and "Analyse arrêtée" in status
    assert len(verdicts) == 1 and queue.count("Non analysé") == 2
    assert next(frames, None) is None
    resumed = run_batch(verdicts)[-1][0]
    assert resumed.startswith("✅ **2 message(s) analysé(s)**")
