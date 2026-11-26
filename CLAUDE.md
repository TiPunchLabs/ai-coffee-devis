# CLAUDE.md — ai-coffee-devis

Live demo for AI Coffee (Guadeloupe, 26/11/2026): which emails sent to an event-equipment rental company deserve a callback about a new rental? A local Ollama model classifies emails; a Gradio UI shows a prepared corpus and a live AgentMail inbox.

## Project Type

Python application (Gradio UI, flat layout, not a package: `[tool.uv] package = false`).

## Commands

```bash
uv sync --locked                 # install from uv.lock (fails if the lock is stale)
uv run python app.py             # UI on http://127.0.0.1:7860 (GRADIO_SERVER_PORT to change)
uv run python live_inbox.py      # AgentMail connection check, never prints the key
uv run pytest -q                 # 15 tests, no network (Ollama and AgentMail are mocked)
uv run ruff check . && uv run ruff format --check .
```

Live tab credentials come from `pass` through `.envrc` (direnv). Without direnv loaded, start with `direnv exec . uv run python app.py`. Never print, log or ask for `AGENTMAIL_API_KEY`.

## Structure

```
app.py            # Gradio UI: prepared work queue + live AgentMail tab (list + detail)
core.py           # corpus, « devis » keyword baseline, shared Ollama classifier, quote check, score
live_inbox.py     # read-only AgentMail client (3 GETs), dedup by message_id, French errors
messages.csv      # 20 fictional emails (id;objet;message) — do not edit; answer key 02, 07, 13, 17
tests/            # pytest for core.py and live_inbox.py
docs/             # AGENTMAIL.md, STACK.md, architecture.md, development.md, adr/ (0001-0010)
```

## Rules that must not regress

- Everything user-facing is in **French** (UI, errors, docs). Code, identifiers and comments stay in English.
- One classifier (`core.classify`) for both tabs. The model receives only `{"objet", "message"}`: never the ID, the answer key or the sender.
- A request counts only if its quote is found verbatim in the email (`locate_quote`); otherwise it is « À vérifier ».
- The answer key stays hidden until « 3 · Révéler le corrigé »; a score exists only for a complete 20-email run; a new run clears the old score.
- AgentMail is **read-only**, dedicated AI Coffee inbox only (never Scout's). Email content is untrusted: escape it, show plain text, never show the sender.
- Gradio binds to `127.0.0.1` with `share=False`. Fonts are system fonts: the prepared demo must work offline.
- Prompts can be edited per browser session from « ⚙ Paramètres » (never saved, only {objet}/{message} placeholders, see ADR 0010); `core.PROMPT` and `core.USER_TEMPLATE` stay the validated defaults.
- Changing the default prompt or the model requires re-running the 20 emails: reference result is 4/4 found, 0 false alarm with `gemma4:e2b`.

## Code Style

- Python 3.12, full type hints, docstrings on every function, Ruff (`line-length = 120`).
- Gradio 6 APIs: `css`/`theme` are passed to `launch()`; the clickable lists use `gr.HTML` + `js_on_load` + `trigger('select')`.
- Decisions are recorded in `docs/adr/`; add a new ADR instead of rewriting an accepted one.
- No auto-commit; Conventional Commits when asked.
