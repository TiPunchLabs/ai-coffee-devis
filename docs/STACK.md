# 🛠️ Technologies utilisées · AI Coffee Devis

> **Objectif** : lister chaque technologie du projet, sa version, son rôle et la raison de son choix. Les décisions détaillées sont dans [docs/adr/](adr/README.md).

## 🧠 Vue d'ensemble

```
             ┌──────────────── portable du présentateur (hors ligne possible) ────────────────┐
navigateur ──► Gradio (127.0.0.1:7860) ──► core.py ──► openai ──► Ollama /v1 (127.0.0.1:11434) ──► gemma4:e2b
             │        │                                                                         │
             │        └──► live_inbox.py ──► httpx ──(Internet, GET seulement)──► AgentMail API v0
             │                    ▲                                                             │
             │       direnv + pass (.envrc) exporte AGENTMAIL_API_KEY / AGENTMAIL_INBOX_ID      │
             └────────────────────────────────────────────────────────────────────────────────┘
```

------

## 1. Exécution

| Technologie | Version | Rôle | Pourquoi | ADR |
|---|---|---|---|---|
| Python | 3.12.12 (`.python-version` : `3.12`, `requires-python >=3.12,<3.13`) | langage de l'application | stable, compatible avec Gradio 6 | [0001](adr/0001-uv-pour-python-et-les-dependances.md) |
| uv | 0.13.5 (installé via mise) | Python, environnement virtuel, dépendances, verrouillage (`uv.lock`) | une seule commande reproductible : `uv sync --locked` | [0001](adr/0001-uv-pour-python-et-les-dependances.md) |
| Gradio | 6.32.0 | interface web à deux onglets, streaming de la progression | interface en quelques lignes, écoute locale seulement | [0003](adr/0003-gradio-en-local-uniquement.md) |
| openai | 3.49.0 | client du classifieur, branché sur l'API compatible OpenAI d'Ollama (`/v1`) | client standard, erreurs typées, même code pour un autre serveur compatible | [0009](adr/0009-client-openai-pour-ollama.md) |
| httpx | 0.28.1 | appels HTTP vers AgentMail ; transport simulé des tests | timeouts explicites, `MockTransport` pour les tests | — |

## 2. Intelligence artificielle locale

| Technologie | Version | Rôle | Pourquoi | ADR |
|---|---|---|---|---|
| Ollama | 0.40.16 | serveur de modèles local (API compatible OpenAI `/v1/chat/completions`) | inférence sur le portable, sans Internet | [0002](adr/0002-ollama-local-avec-gemma4-e2b.md) |
| gemma4:e2b | ID `b37049369adf`, 4,6 Go | classifieur partagé par les deux onglets | 4/4 demandes, 0 fausse alerte, ~3 s à chaud sur le corpus | [0002](adr/0002-ollama-local-avec-gemma4-e2b.md) |
| Sortie structurée | schéma JSON passé dans `response_format` (`json_schema`) | force `{"demande": bool, "citation": str}` | réponse analysable, citation vérifiée dans le courriel | [0004](adr/0004-classifieur-partage-et-citation-verifiee.md) |

Paramètres d'appel : `temperature=0`, `reasoning_effort="none"` (pas de raisonnement préalable), `keep_alive: "30m"` (extension Ollama passée dans `extra_body`), délai de 180 s, aucune nouvelle tentative automatique. Modifiable par `OLLAMA_MODEL` et `OLLAMA_URL`.

## 3. Courriels en direct

| Technologie | Version | Rôle | Pourquoi | ADR |
|---|---|---|---|---|
| AgentMail | API REST v0 (`https://api.agentmail.to/v0`) | boîte dédiée AI Coffee qui reçoit les messages du public | adresse prête à l'emploi, lecture par API | [0005](adr/0005-agentmail-en-lecture-seule.md) |

Trois lectures seulement : boîte, liste des messages (paginée), un message. Aucun envoi, aucune suppression, aucun marquage.

## 4. Secrets et configuration

| Technologie | Version | Rôle | Pourquoi | ADR |
|---|---|---|---|---|
| pass | — | coffre chiffré (GPG) des valeurs AgentMail | convention de tous les projets de l'auteur | [0006](adr/0006-secrets-via-direnv-et-pass.md) |
| direnv | 2.38.2 | exporte les variables à l'entrée du dossier via `.envrc` | aucun secret sur le disque en clair | [0006](adr/0006-secrets-via-direnv-et-pass.md) |

| Variable | Source | Défaut |
|---|---|---|
| `AGENTMAIL_API_KEY` | `pass agentmail/ai-coffee-api-key` | aucun (onglet direct indisponible) |
| `AGENTMAIL_INBOX_ID` | `pass agentmail/ai-coffee-inbox-id` | aucun |
| `OLLAMA_MODEL` | environnement | `gemma4:e2b` |
| `OLLAMA_URL` | environnement | `http://127.0.0.1:11434` |
| `GRADIO_SERVER_PORT` | environnement | `7860` |

## 5. Qualité

| Technologie | Version | Rôle |
|---|---|---|
| pytest | 9.2.0 | 15 tests : corpus, mot-clé, citations, classifieur simulé, connecteur AgentMail simulé (`uv run pytest -q`) |
| Ruff | 0.17.6 | lint et formatage, `line-length = 120` (`uv run ruff check .`) |
| pre-commit | via `uv tool run` | hooks locaux : fichiers, YAML (yamllint), gitleaks, Ruff |
| gitleaks | 8.30.1 | recherche de secrets : hook pre-commit et job CI sur tout l'historique |
| GitHub Actions | checkout v7.0.1, setup-uv v10.3.3 | CI : formatage, Ruff, tests, gitleaks (`.github/workflows/ci.yml`) |

## 6. Données

| Fichier | Format | Contenu |
|---|---|---|
| `messages.csv` | CSV UTF-8, séparateur `;`, colonnes `id;objet;message` | 20 courriels fictifs ; corrigé fixé dans `core.py` (02, 07, 13, 17), jamais envoyé au modèle |

------

> **Document créé le** : 26/11/2026
> **Version** : 1.0
