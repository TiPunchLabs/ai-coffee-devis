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

Le hook **gitleaks** (v8.30.1) analyse les modifications indexées à chaque commit et refuse le commit si un secret est détecté (clé d'API, jeton, clé privée). Ce hook ne regarde que l'index : `--all-files` n'y change rien. Pour analyser **tout l'historique** en local, avec la même commande que le job CI `secrets` :

```bash
uv tool run pre-commit run gitleaks-history --hook-stage manual   # gitleaks git --redact --verbose .
```

## 4. Intégration continue (GitHub Actions)

Fichier : `.github/workflows/ci.yml`, déclenché à chaque push sur `main` et à chaque pull request vers `main`.

| Job | Étapes | Échoue si |
|---|---|---|
| `quality` | `uv sync --locked`, `ruff format --check --diff`, `ruff check`, `pytest -q`, hooks pre-commit (sauf gitleaks et Ruff, déjà couverts) | `uv.lock` périmé, code mal formaté, erreur Ruff, test en échec, YAML invalide, clé privée, fin de ligne |
| `secrets` | gitleaks v8.30.1 (somme SHA-256 vérifiée), analyse de **tout l'historique** git | un secret est trouvé dans n'importe quel commit |

Les actions sont figées par empreinte de commit (`actions/checkout` v7.0.1, `astral-sh/setup-uv` v10.3.3), les pull requests annulent leurs anciennes exécutions mais jamais celles de `main`, et uv est en 0.13.5 : la version est imposée par `required-version` dans `pyproject.toml`, que setup-uv lit en CI et que uv vérifie en local (un uv d'une autre version refuse de travailler sur le projet). Permissions minimales : `contents: read`. Les tests n'ont pas besoin d'Ollama ni d'AgentMail (simulés).

Reproduire la CI en local :

```bash
uv sync --locked
uv run ruff format --check --diff . && uv run ruff check . && uv run pytest -q
uv tool run pre-commit run --all-files                            # hooks run by the quality job
uv tool run pre-commit run gitleaks-history --hook-stage manual  # same scan as the secrets job
```

## 5. Conventions

- Textes visibles en **français** ; code, identifiants et commentaires en anglais.
- Annotations de type partout, docstring sur chaque fonction, Ruff `line-length = 120`.
- Ne pas modifier `messages.csv` ni le corrigé.
- Après un changement du prompt ou du modèle, relancer les 20 messages et comparer à la référence (4/4, 0 fausse alerte).
- Toute décision structurante → nouvel ADR dans `docs/adr/`.
- Pas de commit automatique ; messages au format Conventional Commits.

## 6. Dépannage développeur

| Symptôme | Cause | Action |
|---|---|---|
| `uv: command not found` dans un terminal neuf | mise pas encore activé | ouvrir un nouveau prompt, ou `mise exec -- uv …` |
| `lockfile needs to be updated` | `pyproject.toml` modifié | `uv lock`, puis `uv sync --locked` |
| Onglet en direct : « Configuration AgentMail absente » | lancé sans direnv | `direnv allow`, puis `direnv exec . uv run python app.py` |
| `Address already in use` | instance déjà lancée | README section 3.3 |
