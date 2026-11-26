# 🛠️ Développement · AI Coffee Devis

> **Prérequis** : Ubuntu 24.04, uv (via mise), Ollama avec `gemma4:e2b`, direnv + pass pour l'onglet en direct. Installation complète : [README, section 2](../README.md#2-installation-ubuntu-2404-une-seule-fois-avec-internet).

## 1. Commandes

```bash
uv sync --locked                       # install exactly what uv.lock pins
uv run python app.py                   # app on http://127.0.0.1:7860
direnv exec . uv run python app.py     # same, with AgentMail credentials from pass
uv run python live_inbox.py            # AgentMail connection check (key never printed)
uv run pytest -q                       # tests (no network)
uv run ruff check . && uv run ruff format --check .
uv tool run pre-commit run --all-files # all hooks (needs a git repository)
```

Arrêter l'application ou libérer le port : [README, section 3.3](../README.md#33-arrêter-lapplication).

## 2. Tests

| Fichier | Couvre | Réseau |
|---|---|---|
| `tests/test_core.py` | corpus, mot « devis », citation, contenu envoyé au modèle, erreurs Ollama | Ollama simulé |
| `tests/test_live_inbox.py` | pagination, déduplication, messages envoyés ignorés, expéditeur masqué, erreurs HTTP et réseau, HTML | AgentMail simulé (`httpx.MockTransport`) |

L'interface (`app.py`) n'a pas de test automatique : après une modification, refaire le parcours de [README, section 3.1](../README.md#31-premier-test-sans-agentmail-ni-secret) et vérifier l'onglet en direct (README section 3.2).

## 3. Pre-commit

```bash
uv tool run pre-commit install           # once, after git init
uv tool run pre-commit run --all-files
```

Les hooks Ruff appellent `uv run ruff` : ils utilisent la version verrouillée dans `uv.lock` (0.17.6), la même que la commande manuelle.

## 4. Conventions

- Textes visibles en **français** ; code, identifiants et commentaires en anglais.
- Annotations de type partout, docstring sur chaque fonction, Ruff `line-length = 120`.
- Ne pas modifier `messages.csv` ni le corrigé.
- Après un changement du prompt ou du modèle, relancer les 20 messages et comparer à la référence (4/4, 0 fausse alerte).
- Toute décision structurante → nouvel ADR dans `docs/adr/`.
- Pas de commit automatique ; messages au format Conventional Commits.

## 5. Dépannage développeur

| Symptôme | Cause | Action |
|---|---|---|
| `uv: command not found` dans un terminal neuf | mise pas encore activé | ouvrir un nouveau prompt, ou `mise exec -- uv …` |
| `lockfile needs to be updated` | `pyproject.toml` modifié | `uv lock`, puis `uv sync --locked` |
| Onglet en direct : « Configuration AgentMail absente » | lancé sans direnv | `direnv allow`, puis `direnv exec . uv run python app.py` |
| `Address already in use` | instance déjà lancée | README section 3.3 |
