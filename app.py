"""AI Coffee demo: which emails deserve a callback about a new rental?

Entry point: `uv run python app.py`, then open http://127.0.0.1:7860
"""

from __future__ import annotations

import copy
import html
import os
import re
import time
from collections.abc import Iterator

import gradio as gr

from core import (
    DEFAULT_MODEL,
    EXPECTED,
    EXPECTED_LABELS,
    MODIFICATION,
    NEW_RENTAL,
    OTHER,
    PROMPT,
    USER_TEMPLATE,
    AnalysisError,
    Mail,
    PromptError,
    ServiceError,
    Verdict,
    check_prompts,
    classify,
    keyword_matches,
    load_corpus,
    score,
)
from live_inbox import LiveMail, Mailbox, MailboxError, local_time

MAILS = load_corpus()
MAIL_BY_ID = {m.id: m for m in MAILS}
SUBJECTS = {m.id: m.subject for m in MAILS}
KEYWORD_IDS = frozenset(m.id for m in keyword_matches(MAILS))
MAILBOX = Mailbox()

Run = dict | None
Board = dict
Outcome = dict  # {"contract": 2, "category": nouvelle_location | modification_location | autre | error, "quote", ...}

# Version of the analysis contract stored in each outcome. Results from another version (e.g. the old
# two-field demande/citation answer) cannot say whether a message is a modification: they are ignored
# and the message shows « Non analysé » until it is analysed again.
CONTRACT = 2
ERROR = "error"
LABELS = {
    NEW_RENTAL: "Nouvelle demande de location",
    MODIFICATION: "Modification de location",
    OTHER: "Hors périmètre",
    ERROR: "Analyse à vérifier",
}
NEXT_STEPS = {
    NEW_RENTAL: "Vérifier la disponibilité du matériel et préparer une réponse.",
    MODIFICATION: "Vérifier si la modification est possible et répondre au client.",
    OTHER: "Aucune location à préparer ni à modifier. Si le courriel pose une question, y répondre normalement.",
    ERROR: "Lire le courriel ci-dessous et décider soi-même, ou relancer l’analyse.",
}

EMPTY_BOARD: Board = {"results": {}, "keyword": False, "revealed": False, "progress": None}


# ---------------------------------------------------------------- analysis outcomes


def outcome_from(verdict: Verdict, info: str = "") -> Outcome:
    """Stored result of a successful analysis."""
    return {"contract": CONTRACT, "category": verdict.category, "quote": verdict.quote, "info": info}


def error_outcome(err: Exception) -> Outcome:
    """Stored result of an analysis that needs review (never counted as classified)."""
    return {"contract": CONTRACT, "category": ERROR, "quote": "", "error": str(err)}


def current(outcome: Outcome | None) -> Outcome | None:
    """Outcome usable with the current contract, or None (not analysed, or stale format)."""
    return outcome if outcome and outcome.get("contract") == CONTRACT else None


def tally(outcomes: list[Outcome | None]) -> dict[str, int]:
    """Counters derived from the analysis state: one entry per message, so re-analysis never double counts."""
    cats = [o["category"] for o in map(current, outcomes) if o]
    return {
        "to_process": sum(c in (NEW_RENTAL, MODIFICATION) for c in cats),
        "new": cats.count(NEW_RENTAL),
        "modification": cats.count(MODIFICATION),
        "other": cats.count(OTHER),
        "error": cats.count(ERROR),
    }


def counters_html(counts: dict[str, int]) -> list[str]:
    """« À traiter » first, then new inquiries (the only ones counted as new requests)."""
    parts = [
        f"<span class='q-count'>{counts['to_process']} à traiter</span>",
        f"{counts['new']} nouvelle(s) demande(s) de location",
    ]
    if counts["error"]:
        parts.append(f"{counts['error']} à vérifier")
    return parts


# ---------------------------------------------------------------- rendering helpers


def esc(text: str) -> str:
    """Escape untrusted email text for HTML display."""
    return html.escape(text, quote=True)


BADGES = {
    NEW_RENTAL: ("attention", "● "),
    MODIFICATION: ("attention", "◆ "),
    ERROR: ("attention", "▲ "),
    OTHER: ("muted", ""),
}


def badge(outcome: Outcome | None, pending: str) -> str:
    """Status pill: the label carries the meaning, colour only reinforces it (amber = à traiter)."""
    outcome = current(outcome)
    if outcome is None:
        return f'<span class="q-badge q-badge--muted">{pending}</span>'
    tone, mark = BADGES[outcome["category"]]
    return f'<span class="q-badge q-badge--{tone}">{mark}{LABELS[outcome["category"]]}</span>'


def quote_of(outcome: Outcome | None) -> str:
    """Verified customer quote for a message to process, else ""."""
    outcome = current(outcome)
    return outcome["quote"] if outcome and outcome["category"] in (NEW_RENTAL, MODIFICATION) else ""


def second_line(outcome: Outcome | None, body: str) -> str:
    """Row preview: the customer's request when there is one, else the start of the email."""
    if quote_of(outcome):
        return f"« {esc(preview(quote_of(outcome), 90))} »"
    if current(outcome) and current(outcome)["category"] == ERROR:
        return "Réponse du modèle à vérifier"
    return esc(preview(body))


def highlight(body: str, quote: str = "", keyword: bool = False) -> str:
    """Escaped body with the verified quote marked and, optionally, the word « devis » underlined."""
    text = esc(body)
    if quote:
        span = esc(quote)
        start = text.find(span)
        if start >= 0:
            text = f"{text[:start]}<mark class='q-quote'>{span}</mark>{text[start + len(span) :]}"
    if keyword:
        text = re.sub(r"\b(devis)\b", r"<span class='q-kw'>\1</span>", text, flags=re.IGNORECASE)
    return text


def preview(text: str, limit: int = 110) -> str:
    """First characters of a text on one line."""
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def request_section(outcome: Outcome | None, pending: str) -> str:
    """« Ce que demande le client » block, then the next step for the operator."""
    outcome = current(outcome)
    if outcome is None:
        what, todo = f"<p class='q-muted'>{pending}</p>", ""
    else:
        category = outcome["category"]
        todo = NEXT_STEPS[category]
        if category in (NEW_RENTAL, MODIFICATION):
            what = (
                f"<p class='q-kind'>{LABELS[category]}</p>"
                f"<blockquote class='q-ask'>« {esc(outcome['quote'])} »</blockquote>"
                "<p class='q-note'>Extrait recopié par le modèle et retrouvé mot pour mot dans le courriel.</p>"
            )
        elif category == ERROR:
            what = f"<p>Analyse à vérifier : {esc(outcome['error'])}.</p>"
        else:
            what = (
                "<p>Hors périmètre : le modèle ne voit ni nouvelle demande de location, "
                "ni modification d’une location existante.</p>"
            )
    next_step = f"<p class='q-next'><strong>Prochaine étape suggérée</strong> · {todo}</p>" if todo else ""
    return f"<section class='q-section'><h3>Ce que demande le client</h3>{what}{next_step}</section>"


def queue_html(rows: list[str], header: str, empty: str) -> str:
    """List wrapper shared by both tabs."""
    items = "".join(rows) or f"<p class='q-empty'>{empty}</p>"
    return f"<div class='q-head'>{header}</div><div class='q-items' role='list'>{items}</div>"


def row_html(item_id: str, meta: str, subject: str, second: str, pill: str, selected: bool, extra: str = "") -> str:
    """One selectable row (a real button: keyboard and screen-reader friendly)."""
    current = " aria-current='true'" if selected else ""
    cls = "q-row is-selected" if selected else "q-row"
    return (
        f"<div role='listitem'><button type='button' class='{cls}' data-id='{esc(item_id)}'{current}>"
        f"<span class='q-row-top'><span class='q-meta'>{meta}</span>{pill}</span>"
        f"<span class='q-subject'>{esc(subject)}</span>"
        f"<span class='q-second'>{second}</span>{extra}</button></div>"
    )


def select_js(detail_id: str) -> str:
    """Click delegation: instant selection feedback, event to Python, scroll to details on phones."""
    return (
        "element.addEventListener('click', (e) => {"
        " const b = e.target.closest('button[data-id]'); if (!b) return;"
        " element.querySelectorAll('.q-row.is-selected').forEach(r => {"
        "  r.classList.remove('is-selected'); r.removeAttribute('aria-current'); });"
        " b.classList.add('is-selected'); b.setAttribute('aria-current', 'true');"
        " trigger('select', {id: b.dataset.id});"
        " if (window.matchMedia('(max-width: 767px)').matches) setTimeout(() =>"
        f"  document.getElementById('{detail_id}')?.scrollIntoView({{block: 'start'}}), 150);"
        "});"
    )


# ---------------------------------------------------------------- editable prompts


def prompts_changed(system_prompt: str, user_template: str) -> bool:
    """True when the session prompts differ from the validated project prompts."""
    return system_prompt != PROMPT or user_template != USER_TEMPLATE


def prompt_flag(system_prompt: str, user_template: str) -> str:
    """Header badge shown while modified prompts are in use (text, not colour only)."""
    if not prompts_changed(system_prompt, user_template):
        return ""
    return "<span class='q-badge q-badge--attention' role='status'>▲ Prompts modifiés</span>"


def prompt_check(system_prompt: str, user_template: str) -> str:
    """Validation note under the prompt editors."""
    try:
        check_prompts(system_prompt, user_template)
    except PromptError as err:
        return f"⛔ {err}"
    if prompts_changed(system_prompt, user_template):
        return "▲ Prompts modifiés, valides : ils s’appliqueront à la prochaine analyse (cette session seulement)."
    return "✅ Prompts d’origine du projet."


def reset_prompts() -> tuple[str, str]:
    """Restore the exact project prompts."""
    return PROMPT, USER_TEMPLATE


def on_prompts_change(system_prompt: str, user_template: str, board: Board, selected: str | None) -> tuple:
    """A prompt edit makes previous results stale: clear score, answer key and statuses."""
    board = copy.deepcopy(EMPTY_BOARD) | {"keyword": board["keyword"]}
    if prompts_changed(system_prompt, user_template):
        status = "▲ **Prompts modifiés** : l’ancien score est effacé. Relance l’analyse pour voir leur effet."
    else:
        status = "Prompts d’origine rétablis : l’ancien score est effacé. Relance l’analyse."
    return (
        prompt_flag(system_prompt, user_template),
        prompt_check(system_prompt, user_template),
        status,
        None,
        panel(""),
        *views(board, selected),
    )


# ---------------------------------------------------------------- prepared demo


def check_mark(mail_id: str, outcome: Outcome | None) -> str:
    """After the reveal: compare the model with the answer key, in words."""
    expected = mail_id in EXPECTED
    outcome = current(outcome)
    if outcome is None:
        return "Corrigé : nouvelle demande" if expected else "Corrigé : pas une nouvelle demande"
    found = outcome["category"] == NEW_RENTAL
    if not expected and outcome["category"] == MODIFICATION:
        return "Modification de location (hors score)"
    if expected and found:
        return "✓ Bonne détection"
    if expected:
        return "✗ Demande manquée"
    if found:
        return "✗ Fausse alerte"
    return "✓ Bien écarté"


def prepared_header(board: Board) -> str:
    """Counts computed from what the list shows."""
    results = board["results"]
    parts = [f"<strong>{len(MAILS)} messages</strong>"]
    if board["keyword"]:
        parts.append(f"{len(KEYWORD_IDS)} contiennent « devis »")
    if results or board["progress"]:
        parts += counters_html(tally(list(results.values())))
        if board["progress"]:
            parts.append(board["progress"])
    return " · ".join(parts)


def prepared_queue(board: Board, selected: str | None) -> str:
    """The 20 prepared emails as a work queue."""
    pending = "En attente" if board["progress"] == "analyse en cours" else "Non analysé"
    rows = []
    for mail in MAILS:
        outcome = board["results"].get(mail.id)
        tags = "<span class='q-tag'>« devis »</span>" if board["keyword"] and mail.id in KEYWORD_IDS else ""
        second = second_line(outcome, mail.body)
        extra = f"<span class='q-check'>{check_mark(mail.id, outcome)}</span>" if board["revealed"] else ""
        rows.append(
            row_html(
                mail.id,
                f"Nº {mail.id} {tags}",
                mail.subject,
                second,
                badge(outcome, pending),
                mail.id == selected,
                extra,
            )
        )
    return queue_html(rows, prepared_header(board), "")


def prepared_detail(board: Board, selected: str | None) -> str:
    """Selected email: request first, then the original email for comparison."""
    mail: Mail | None = MAIL_BY_ID.get(selected or "")
    if not mail:
        return "<div class='q-detail-empty'>Choisis un message dans la liste.</div>"
    outcome = board["results"].get(mail.id)
    keyword = board["keyword"] and mail.id in KEYWORD_IDS
    pending = "Pas encore analysé. Clique « 2 · Analyser les 20 messages »."
    reveal_line = ""
    if board["revealed"]:
        label = f"nouvelle demande ({EXPECTED_LABELS[mail.id]})" if mail.id in EXPECTED else "pas une nouvelle demande"
        reveal_line = f"<p class='q-reveal'><strong>Corrigé</strong> · {label} · {check_mark(mail.id, outcome)}</p>"
    kw_line = "<span class='q-tag'>contient « devis »</span>" if keyword else ""
    quote = quote_of(outcome)
    return (
        "<a class='q-back' href='#prep-queue'>← Retour à la liste</a>"
        f"<div class='q-detail-head'><span class='q-meta'>Message Nº {mail.id} {kw_line}</span>"
        f"{badge(outcome, 'Non analysé')}</div>"
        f"<h2 class='q-title'>{esc(mail.subject)}</h2>{reveal_line}"
        f"{request_section(outcome, pending)}"
        "<section class='q-section'><h3>Courriel d’origine</h3>"
        f"<div class='q-mail'><p class='q-mail-subject'>Objet : {esc(mail.subject)}</p>"
        f"<div class='q-body'>{highlight(mail.body, quote, keyword)}</div></div></section>"
    )


def panel(text: str) -> gr.Markdown:
    """Answer-key panel, hidden while empty."""
    return gr.Markdown(value=text, visible=bool(text))


def views(board: Board, selected: str | None) -> tuple[Board, str, str]:
    """State plus both rendered panes."""
    return board, prepared_queue(board, selected), prepared_detail(board, selected)


def select_prepared(board: Board, evt: gr.EventData) -> tuple[str, str]:
    """Remember the clicked email and show it."""
    selected = (evt._data or {}).get("id")
    selected = selected if selected in MAIL_BY_ID else None
    return selected, prepared_detail(board, selected)


def search_keyword(board: Board, selected: str | None) -> tuple[Board, str, str]:
    """Tag the emails containing the whole word « devis »."""
    board = copy.deepcopy(board)
    board["keyword"] = True
    return views(board, selected)


def run_analysis(
    model: str, system_prompt: str, user_template: str, board: Board, selected: str | None
) -> Iterator[tuple]:
    """Classify the 20 prepared emails one by one, streaming progress.

    Yields (status, completed run or None, cleared answer-key panel, board, queue, detail).
    The run is only stored once all 20 emails have been processed.
    Unusable prompts stop everything before any call to the model.
    """
    try:
        check_prompts(system_prompt, user_template)
    except PromptError as err:
        yield (
            f"⛔ **Analyse impossible** : {err} Aucun message n’a été envoyé au modèle.",
            None,
            panel(""),
            *views(board, selected),
        )
        return
    custom = prompts_changed(system_prompt, user_template)
    board = copy.deepcopy(EMPTY_BOARD) | {"keyword": board["keyword"], "progress": "analyse en cours"}
    results = board["results"]
    found: set[str] = set()
    errors: dict[str, str] = {}
    start = time.monotonic()
    yield (
        f"⏳ Analyse lancée avec `{model.strip()}`… (score précédent effacé)",
        None,
        panel(""),
        *views(board, selected),
    )
    for index, mail in enumerate(MAILS, 1):
        try:
            verdict = classify(mail.subject, mail.body, model, system_prompt, user_template)
        except ServiceError as err:
            message = (
                f"⛔ **Analyse interrompue au message {mail.id}** ({index - 1}/{len(MAILS)} traités). "
                f"{err} Aucun score n’est calculé."
            )
            board["progress"] = "analyse incomplète"
            yield message, None, panel(""), *views(board, selected)
            return
        except AnalysisError as err:
            errors[mail.id] = str(err)
            results[mail.id] = error_outcome(err)
        else:
            if verdict.is_new_rental:
                found.add(mail.id)
            results[mail.id] = outcome_from(verdict)
        elapsed = time.monotonic() - start
        yield f"⏳ {index}/{len(MAILS)} messages analysés · {elapsed:.0f} s", None, panel(""), *views(board, selected)
    elapsed = time.monotonic() - start
    status = (
        f"✅ **Analyse terminée** : {len(MAILS)} messages en {elapsed:.0f} s avec `{model.strip()}` · "
        f"{tally(list(results.values()))['to_process']} à traiter, dont {len(found)} nouvelle(s) demande(s) de location."
    )
    if errors:
        status += f" ⚠️ {len(errors)} message(s) à vérifier : {', '.join(sorted(errors))}."
    if custom:
        status += " ▲ Obtenu avec des **prompts modifiés**."
    run = {
        "model": model.strip(),
        "seconds": round(elapsed),
        "found": sorted(found),
        "errors": errors,
        "custom_prompts": custom,
    }
    board["progress"] = None
    yield status, run, panel(""), *views(board, selected)


def stop_analysis(board: Board, selected: str | None) -> tuple:
    """Mark an interrupted run as incomplete and clear any score."""
    board = copy.deepcopy(board) | {"revealed": False}
    if board["progress"] == "analyse en cours":
        board["progress"] = "analyse incomplète"
    message = "⛔ **Analyse arrêtée.** Elle est incomplète : aucun score. Relance l’étape 2 si besoin."
    return message, None, panel(""), *views(board, selected)


def describe(ids: list[str]) -> str:
    """Format identifiers with their subjects."""
    return ", ".join(f"{i} ({SUBJECTS[i]})" for i in ids) or "aucun"


def score_row(label: str, found_ids: set[str]) -> str:
    """One Markdown table row of the comparison."""
    s = score(found_ids)
    return f"| {label} | {len(s['found'])}/4 | {len(s['false_alarms'])} | {len(s['missed'])} |"


def reveal(run: Run) -> str:
    """Answer key and comparison of both methods."""
    keyword_ids = set(KEYWORD_IDS)
    lines = [
        "### Corrigé · 4 nouvelles demandes de location",
        " · ".join(f"**{i}** {EXPECTED_LABELS[i]}" for i in sorted(EXPECTED)),
        "",
        "| Méthode | Demandes retrouvées | Fausses alertes | Demandes manquées |",
        "|---|---|---|---|",
        score_row("Mot « devis »", keyword_ids),
    ]
    if run:
        custom = " · prompts modifiés" if run.get("custom_prompts") else ""
        lines.append(score_row(f"Modèle local `{run['model']}` ({run['seconds']} s{custom})", set(run["found"])))
    lines.append("")
    kw = score(keyword_ids)
    lines.append(
        f"**Mot « devis »** · fausses alertes : {describe(kw['false_alarms'])} · manquées : {describe(kw['missed'])}"
    )
    if run:
        ai = score(set(run["found"]))
        lines.append(
            f"\n**Modèle local** · fausses alertes : {describe(ai['false_alarms'])} · "
            f"manquées : {describe(ai['missed'])}"
        )
        if run["errors"]:
            lines.append(
                f"\n⚠️ Non classés (erreur d’analyse, comptés comme non retenus) : {describe(sorted(run['errors']))}"
            )
        if run.get("custom_prompts"):
            lines.append("\n▲ **Score obtenu avec des prompts modifiés** (Paramètres), pas avec les prompts d’origine.")
    else:
        lines.append("\n**Modèle local** · pas d’analyse complète : lance l’étape 2 jusqu’au bout.")
    return "\n".join(lines)


def reveal_click(run: Run, board: Board, selected: str | None) -> tuple:
    """Show the answer key panel and mark each row against it."""
    board = copy.deepcopy(board) | {"revealed": True}
    return panel(reveal(run)), *views(board, selected)


# ---------------------------------------------------------------- live demo (AgentMail)


def address_markdown() -> str:
    """Recipient address for the audience (dedicated inbox only)."""
    if MAILBOX.verified_address:
        return f"<p class='q-label'>Écrivez à</p><p class='q-address'>{esc(MAILBOX.verified_address)}</p>"
    configured = os.getenv("AGENTMAIL_INBOX_ID", "").strip()
    if configured:
        return (
            f"<p class='q-label'>Écrivez à</p><p class='q-address'>{esc(configured)}</p>"
            "<p class='q-note'>Adresse lue dans l’environnement (direnv + pass), pas encore confirmée par AgentMail : "
            "clique « Relever les nouveaux messages ».</p>"
        )
    return (
        "<p class='q-label'>Adresse non configurée</p>"
        "<p class='q-note'>Voir <code>docs/AGENTMAIL.md</code>. L’onglet « Démo préparée » fonctionne sans.</p>"
    )


def live_mails() -> list[LiveMail]:
    """Retrieved messages, newest first (same order as the mailbox choices)."""
    return [MAILBOX.messages[mid] for _, mid in MAILBOX.choices()]


def live_queue(verdicts: dict, selected: str | None) -> str:
    """Retrieved messages as a queue: time and subject only, never the sender."""
    mails = live_mails()
    rows = []
    for mail in mails:
        outcome = verdicts.get(mail.message_id)
        if mail.usable:
            second = second_line(outcome, mail.body)
        else:
            second = "Aucun texte lisible (image ou pièce jointe seule)"
        rows.append(
            row_html(
                mail.message_id,
                local_time(mail.timestamp),
                mail.subject or "(sans objet)",
                second,
                badge(outcome, "Non analysé"),
                mail.message_id == selected,
            )
        )
    header = f"<strong>{len(mails)} message(s) relevé(s)</strong>"
    outcomes = [verdicts.get(m.message_id) for m in mails]
    if any(map(current, outcomes)):
        header = " · ".join([header, *counters_html(tally(outcomes))])
    return queue_html(rows, header, "Aucun message relevé. Clique « Relever les nouveaux messages ».")


def show_message(message_id: str | None, verdicts: dict) -> str:
    """Display the selected message as plain text (no sender)."""
    mail = MAILBOX.messages.get(message_id or "")
    if not mail:
        return "<div class='q-detail-empty'>Choisis un message dans la liste.</div>"
    outcome = verdicts.get(mail.message_id)
    pending = "Pas encore analysé. Clique « Analyser ce message avec le modèle local »."
    if not mail.usable:
        pending = "Ce message n’a pas de texte lisible (image ou pièce jointe seule) : il ne peut pas être analysé."
    quote = quote_of(outcome)
    body = highlight(mail.body, quote) if mail.usable else "<em>(aucun texte lisible dans ce message)</em>"
    run_info = (
        f"<p class='q-note'>{esc(current(outcome)['info'])}</p>"
        if current(outcome) and current(outcome).get("info")
        else ""
    )
    return (
        "<a class='q-back' href='#live-queue'>← Retour à la liste</a>"
        f"<div class='q-detail-head'><span class='q-meta'>Reçu à {local_time(mail.timestamp)}</span>"
        f"{badge(outcome, 'Non analysé')}</div>"
        f"<h2 class='q-title'>{esc(mail.subject or '(sans objet)')}</h2>"
        f"{request_section(outcome, pending)}{run_info}"
        "<section class='q-section'><h3>Courriel d’origine</h3>"
        f"<div class='q-mail'><div class='q-body'>{body}</div></div></section>"
    )


def fetch_messages(current: str | None, verdicts: dict) -> tuple:
    """Retrieve new messages from AgentMail, keeping earlier ones selectable."""
    try:
        _, status = MAILBOX.fetch()
        status = f"✅ {status}"
    except MailboxError as err:
        status = f"⚠️ {err}"
    selected = current if current in MAILBOX.messages else None
    return (
        status,
        address_markdown(),
        selected,
        live_queue(verdicts, selected),
        show_message(selected, verdicts),
        gr.Button(visible=selected is not None),
    )


def select_live(verdicts: dict, evt: gr.EventData) -> tuple[str | None, str, gr.Button, str]:
    """Remember the clicked message and display it."""
    selected = (evt._data or {}).get("id")
    selected = selected if selected in MAILBOX.messages else None
    return selected, show_message(selected, verdicts), gr.Button(visible=selected is not None), ""


def analyze_live(
    message_id: str | None, model: str, system_prompt: str, user_template: str, verdicts: dict
) -> tuple[str, dict, str, str]:
    """Run the shared classifier on one live message. Returns (status, verdicts, queue, detail)."""
    mail = MAILBOX.messages.get(message_id or "")
    if not mail:
        return "Choisis d’abord un message dans la liste.", verdicts, live_queue(verdicts, None), show_message(None, {})
    if not mail.usable:
        status = (
            "⚠️ Ce message n’a pas de texte lisible (image ou pièce jointe seule). "
            "Demande à l’expéditeur d’écrire directement dans le corps du courriel."
        )
        return status, verdicts, live_queue(verdicts, message_id), show_message(message_id, verdicts)
    verdicts = dict(verdicts)
    start = time.monotonic()
    try:
        verdict = classify(mail.subject, mail.body, model, system_prompt, user_template)
    except ServiceError as err:
        return f"⛔ {err}", verdicts, live_queue(verdicts, message_id), show_message(message_id, verdicts)
    except AnalysisError as err:
        verdicts[mail.message_id] = error_outcome(err)
        status = f"⚠️ Analyse à vérifier : {err}. Relance ou juge toi-même."
    else:
        seconds = time.monotonic() - start
        info = f"Modèle {model.strip()}, {seconds:.1f} s."
        if prompts_changed(system_prompt, user_template):
            info += " Prompts modifiés."
        verdicts[mail.message_id] = outcome_from(verdict, info)
        mark = "➖" if verdict.category == OTHER else "✅"
        status = f"{mark} {LABELS[verdict.category]} · {info}"
    return status, verdicts, live_queue(verdicts, message_id), show_message(message_id, verdicts)


# ---------------------------------------------------------------- layout

CSS = """
.gradio-container { max-width: 1320px !important; }
#app-header { align-items: flex-end; gap: 16px; }
#header-actions { align-items: center; justify-content: flex-end; gap: 10px; flex-wrap: nowrap; }
#header-actions > * { flex: 0 0 auto !important; min-width: 0 !important; width: auto !important; }
#prompt-flag:empty { display: none; }
.q-settings-title { font-size: 1.15rem; font-weight: 650; margin: 0 0 4px; }
.q-settings-note { font-size: 0.85rem; color: var(--body-text-color-subdued); }
#settings input:focus-visible, #settings textarea:focus-visible, #settings button:focus-visible,
#settings-btn:focus-visible { outline: 2px solid var(--color-accent) !important; outline-offset: 2px; }
#system-prompt textarea, #user-template textarea { font-family: var(--font-mono); font-size: 0.85rem; line-height: 1.45; }
#app-title h1 { font-size: 1.5rem; font-weight: 650; letter-spacing: -0.01em; margin: 0; }
#app-title p { margin: 2px 0 0; color: var(--body-text-color-subdued); font-size: 0.95rem; }
.toolbar { gap: 8px; flex-wrap: wrap; }
.toolbar button { flex: 0 1 auto !important; min-width: 0 !important; }
.run-status { font-size: 0.95rem; }
.run-status p { margin: 0; }
.score-panel { background: var(--background-fill-primary); border: 1px solid var(--border-color-primary) !important;
  border-radius: 10px; padding: 12px 18px !important; }
.score-panel h3 { margin-top: 0; }

/* queue */
#prep-queue, #live-queue { border: 1px solid var(--border-color-primary); border-radius: 10px;
  background: var(--background-fill-primary); max-height: calc(100vh - 230px); overflow-y: auto !important; padding: 0 !important; }
.q-head { position: sticky; top: 0; z-index: 1; background: var(--background-fill-primary);
  padding: 10px 14px; border-bottom: 1px solid var(--border-color-primary); font-size: 0.9rem;
  color: var(--body-text-color-subdued); }
.q-head strong { color: var(--body-text-color); }
.q-count { color: var(--q-amber-text); font-weight: 600; }
.q-items { display: flex; flex-direction: column; }
.q-row { all: unset; box-sizing: border-box; display: flex; flex-direction: column; gap: 3px; width: 100%;
  padding: 10px 14px 10px 11px; border-left: 3px solid transparent; border-bottom: 1px solid var(--border-color-primary);
  cursor: pointer; }
.q-row:hover { background: var(--background-fill-secondary); }
.q-row.is-selected { background: var(--q-selected-bg); border-left-color: var(--color-accent); }
.q-row:focus-visible, .q-back:focus-visible { outline: 2px solid var(--color-accent); outline-offset: -2px; }
.q-row-top { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.q-meta { font-size: 0.8rem; color: var(--body-text-color-subdued); font-variant-numeric: tabular-nums; }
.q-subject { font-weight: 600; color: var(--body-text-color); overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.q-second { font-size: 0.88rem; color: var(--body-text-color-subdued); overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.q-check { font-size: 0.82rem; font-weight: 600; color: var(--body-text-color); }
.q-empty, .q-detail-empty { padding: 24px 16px; color: var(--body-text-color-subdued); }
.q-badge { flex: none; font-size: 0.78rem; font-weight: 600; padding: 2px 8px; border-radius: 999px;
  border: 1px solid var(--border-color-primary); color: var(--body-text-color-subdued); white-space: nowrap; }
.q-badge--attention { background: var(--q-amber-bg); border-color: var(--q-amber-border); color: var(--q-amber-text); }
.q-tag { font-size: 0.75rem; padding: 0 6px; border-radius: 4px; border: 1px dashed var(--border-color-primary);
  color: var(--body-text-color-subdued); margin-left: 4px; }

/* detail */
#prep-detail, #live-detail { border: 1px solid var(--border-color-primary); border-radius: 10px;
  background: var(--background-fill-primary); padding: 18px 22px; scroll-margin-top: 8px; }
#live-pane { scroll-margin-top: 8px; }
.q-detail-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.q-title { font-size: 1.3rem; font-weight: 650; margin: 6px 0 4px; overflow-wrap: anywhere; }
.q-section { margin-top: 18px; }
.q-section h3 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
  color: var(--body-text-color-subdued); margin: 0 0 8px; }
.q-ask { margin: 0; padding: 10px 14px; border-left: 3px solid var(--q-amber-border); background: var(--q-amber-bg);
  border-radius: 0 8px 8px 0; font-size: 1.1rem; line-height: 1.5; color: var(--body-text-color); }
.q-kind { margin: 0 0 6px; font-weight: 650; color: var(--q-amber-text); }
.q-note { font-size: 0.85rem; color: var(--body-text-color-subdued); margin: 6px 0 0; }
.q-muted { color: var(--body-text-color-subdued); margin: 0; }
.q-next { margin: 12px 0 0; padding-top: 10px; border-top: 1px solid var(--border-color-primary); }
.q-reveal { margin: 4px 0 0; font-size: 0.92rem; }
.q-mail { border: 1px solid var(--border-color-primary); border-radius: 8px; padding: 12px 14px;
  background: var(--background-fill-secondary); }
.q-mail-subject { margin: 0 0 6px; font-weight: 600; font-size: 0.92rem; }
.q-body { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.55; max-height: 45vh; overflow-y: auto; }
mark.q-quote { background: var(--q-amber-bg); color: inherit; box-shadow: inset 0 -2px 0 var(--q-amber-border);
  padding: 0 1px; }
.q-kw { text-decoration: underline; text-decoration-style: wavy; text-underline-offset: 3px; }
.q-back { display: none; font-size: 0.9rem; margin-bottom: 8px; color: var(--color-accent); }
#analyze-btn { margin-bottom: 4px; }

/* live */
#live-address { border: 1px solid var(--border-color-primary); border-radius: 10px; padding: 10px 16px;
  background: var(--background-fill-primary); }
.q-label { margin: 0; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--body-text-color-subdued); }
.q-address { margin: 2px 0 0; font-family: var(--font-mono); font-size: 1.45rem; font-weight: 600;
  overflow-wrap: anywhere; }

:root { --q-amber-bg: #fef3c7; --q-amber-border: #d97706; --q-amber-text: #92400e; --q-selected-bg: #eef2ff; }
.dark { --q-amber-bg: #3b2a06; --q-amber-border: #f59e0b; --q-amber-text: #fcd34d; --q-selected-bg: #1e2540; }

@media (max-width: 767px) {
  .toolbar { display: grid !important; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
  .toolbar button { width: 100%; white-space: normal; font-size: 0.9rem; padding: 8px 10px; }
  .tab-wrapper button { padding-left: 8px !important; padding-right: 8px !important; font-size: 0.9rem !important; }
  .gradio-container { padding-left: 12px !important; padding-right: 12px !important; }
  #prep-queue, #live-queue { max-height: 46vh; }
  #prep-detail, #live-detail { padding: 14px; }
  .q-back { display: inline-block; }
  .q-address { font-size: 1.15rem; }
}
"""


def theme():
    """Quiet neutral theme with one accent colour; system fonts only (works offline)."""

    return gr.themes.Base(
        primary_hue=gr.themes.colors.indigo,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_md,
        font=["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        font_mono=["ui-monospace", "SFMono-Regular", "DejaVu Sans Mono", "Menlo", "Consolas", "monospace"],
    ).set(
        body_background_fill="#f5f6f8",
        body_background_fill_dark="#0f1115",
        button_primary_background_fill="*primary_600",
        button_primary_background_fill_hover="*primary_700",
        button_primary_text_color="white",
        button_large_text_size="*text_md",
        button_large_padding="10px 16px",
        block_shadow="none",
    )


def build():
    """Build the Gradio interface."""

    with gr.Blocks(title="Demandes de devis · AI Coffee") as demo:
        with gr.Row(elem_id="app-header", equal_height=False):
            with gr.Column(scale=1, min_width=300):
                gr.HTML(
                    "<h1>Demandes de devis</h1><p>Location de matériel événementiel · Guadeloupe · "
                    "classement par un modèle d’IA qui tourne sur cet ordinateur</p>",
                    elem_id="app-title",
                    js_on_load=None,
                )
            with gr.Row(elem_id="header-actions", scale=0):
                flag = gr.HTML("", elem_id="prompt-flag", js_on_load=None)
                settings_btn = gr.Button("⚙ Paramètres", variant="secondary", size="sm", elem_id="settings-btn")

        with gr.Sidebar(label="Paramètres", open=False, position="right", width=440, elem_id="settings") as settings:
            gr.HTML("<h2 class='q-settings-title'>Paramètres</h2>", js_on_load=None)
            model = gr.Textbox(
                label="Modèle local (Ollama)",
                info="Nom affiché par `ollama list`",
                value=DEFAULT_MODEL,
                elem_id="model-box",
            )
            show_prompts = gr.Checkbox(label="Afficher et modifier les prompts", value=False, elem_id="show-prompts")
            with gr.Group(visible=False, elem_id="prompt-editor") as prompt_editor:
                system_box = gr.Textbox(
                    label="Prompt système",
                    info="Consignes envoyées au modèle avant chaque courriel.",
                    value=PROMPT,
                    lines=10,
                    max_lines=24,
                    elem_id="system-prompt",
                )
                template_box = gr.Textbox(
                    label="Message utilisateur (gabarit)",
                    info="{objet} et {message} sont remplacés par l’objet et le corps du courriel, encodés en JSON. "
                    "Aucune autre variable n’est acceptée.",
                    value=USER_TEMPLATE,
                    lines=3,
                    max_lines=10,
                    elem_id="user-template",
                )
                reset_btn = gr.Button("Revenir aux prompts d’origine", variant="secondary", size="sm")
                check_note = gr.Markdown(prompt_check(PROMPT, USER_TEMPLATE), elem_id="prompt-check")
            gr.Markdown(
                "Les prompts modifiés valent pour cette fenêtre du navigateur seulement ; "
                "rien n’est enregistré. Un rechargement de la page rétablit les prompts d’origine.",
                elem_classes="q-settings-note",
            )

        with gr.Tab("Démo préparée"):
            board = gr.State(copy.deepcopy(EMPTY_BOARD))
            selected = gr.State("01")
            run_state = gr.State(None)
            with gr.Row(elem_classes="toolbar"):
                keyword_btn = gr.Button("1 · Chercher le mot « devis »", variant="secondary")
                run_btn = gr.Button("2 · Analyser les 20 messages", variant="primary")
                stop_btn = gr.Button("Arrêter l’analyse", variant="secondary")
                reveal_btn = gr.Button("3 · Révéler le corrigé", variant="secondary")
            status = gr.Markdown(elem_classes="run-status")
            summary = gr.Markdown(elem_classes="score-panel", visible=False, container=False)
            with gr.Row(equal_height=False):
                with gr.Column(scale=2, min_width=320):
                    queue = gr.HTML(
                        prepared_queue(EMPTY_BOARD, "01"), elem_id="prep-queue", js_on_load=select_js("prep-detail")
                    )
                with gr.Column(scale=3, min_width=320):
                    detail = gr.HTML(prepared_detail(EMPTY_BOARD, "01"), elem_id="prep-detail", js_on_load=None)

            panes = [board, queue, detail]
            queue.select(select_prepared, board, [selected, detail])
            keyword_btn.click(search_keyword, [board, selected], panes)
            run_evt = run_btn.click(
                run_analysis, [model, system_box, template_box, board, selected], [status, run_state, summary, *panes]
            )
            stop_btn.click(stop_analysis, [board, selected], [status, run_state, summary, *panes], cancels=[run_evt])
            reveal_btn.click(reveal_click, [run_state, board, selected], [summary, *panes])

        with gr.Tab("En direct avec AgentMail"):
            verdicts = gr.State({})
            live_selected = gr.State(None)
            address = gr.HTML(address_markdown(), elem_id="live-address", js_on_load=None)
            gr.Markdown(
                "Envoyez un **courriel fictif** (pas de signature ni de données personnelles) : "
                "une demande à un loueur de matériel… ou pas."
            )
            with gr.Row(elem_classes="toolbar"):
                fetch_btn = gr.Button("Relever les nouveaux messages", variant="primary")
            live_status = gr.Markdown(elem_classes="run-status", elem_id="live-status")
            with gr.Row(equal_height=False):
                with gr.Column(scale=2, min_width=320):
                    live_list = gr.HTML(live_queue({}, None), elem_id="live-queue", js_on_load=select_js("live-pane"))
                with gr.Column(scale=3, min_width=320, elem_id="live-pane"):
                    analyze_btn = gr.Button(
                        "Analyser ce message avec le modèle local",
                        variant="primary",
                        elem_id="analyze-btn",
                        visible=False,
                    )
                    live_detail = gr.HTML(show_message(None, {}), elem_id="live-detail", js_on_load=None)

            fetch_btn.click(
                fetch_messages,
                [live_selected, verdicts],
                [live_status, address, live_selected, live_list, live_detail, analyze_btn],
            )
            live_list.select(select_live, verdicts, [live_selected, live_detail, analyze_btn, live_status])
            analyze_btn.click(
                analyze_live,
                [live_selected, model, system_box, template_box, verdicts],
                [live_status, verdicts, live_list, live_detail],
            )

        settings_btn.click(lambda: gr.Sidebar(open=True), outputs=settings)
        show_prompts.change(lambda show: gr.Group(visible=show), show_prompts, prompt_editor)
        reset_btn.click(reset_prompts, outputs=[system_box, template_box])
        for box in (system_box, template_box):
            box.change(
                on_prompts_change,
                [system_box, template_box, board, selected],
                [flag, check_note, status, run_state, summary, *panes],
                trigger_mode="always_last",
            )
    return demo


if __name__ == "__main__":
    os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
    build().launch(
        server_name="127.0.0.1",
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
        share=False,
        theme=theme(),
        css=CSS,
        footer_links=["gradio", "settings"],
    )
