# 🏗️ Architecture · AI Coffee Devis

> **Objectif** : comprendre en deux minutes comment les modules s'articulent. Les versions sont dans [STACK.md](STACK.md), les choix justifiés dans [adr/](adr/README.md), l'usage dans le [README](../README.md).

## 1. Vue d'ensemble

```
                 ┌──────────────────────────── portable (127.0.0.1) ────────────────────────────┐
 navigateur ───► │ app.py (Gradio)                                                               │
                 │   ├─ onglet « Démo préparée » ──► core.load_corpus()  ◄── messages.csv         │
                 │   │                               core.keyword_matches()                      │
                 │   │                               core.classify() ──► Ollama :11434 (local)   │
                 │   │                               core.score() (corrigé, jamais envoyé)       │
                 │   └─ onglet « En direct » ──► live_inbox.Mailbox.fetch() ──┐                   │
                 │                               core.classify() (le même)    │                   │
                 └────────────────────────────────────────────────────────────┼───────────────────┘
                                                                              │ Internet, GET seulement
                                                                              ▼
                                                                  AgentMail API v0 (boîte AI Coffee)
```

## 2. Modules

| Fichier | Rôle | Dépend de |
|---|---|---|
| `app.py` | Interface : barre d'actions, liste (file de travail) à gauche, détail à droite ; état par session (`gr.State`) | `core`, `live_inbox`, Gradio |
| `core.py` | Corpus, recherche du mot « devis », classifieur Ollama partagé, vérification de la citation, score | httpx |
| `live_inbox.py` | Lecture seule d'AgentMail (boîte, liste paginée, message), déduplication par `message_id`, erreurs en français | httpx |
| `messages.csv` | 20 courriels fictifs ; le corrigé (02, 07, 13, 17) est fixé dans `core.py` | — |

## 3. Flux d'une analyse

1. `app.run_analysis` parcourt les 20 messages et appelle `core.classify(objet, corps, modèle)` pour chacun.
2. `classify` envoie à Ollama `{"objet", "message"}` seulement, avec un schéma JSON imposé (`demande`, `citation`).
3. Si `demande` est vrai, `locate_quote` doit retrouver la citation mot pour mot dans le courriel ; sinon le message passe « À vérifier ».
4. Chaque résultat met à jour la liste en direct (générateur Gradio). Le score n'est conservé que si les 20 messages ont été traités.
5. « 3 · Révéler le corrigé » compare le mot-clé et le modèle au corrigé ; une nouvelle analyse efface l'ancien score.

## 4. Sécurité

| Risque | Mesure | ADR |
|---|---|---|
| Fuite de la clé AgentMail | `pass` + direnv, jamais affichée ni écrite sur disque | [0006](adr/0006-secrets-via-direnv-et-pass.md) |
| Exposition de l'application | `127.0.0.1`, `share=False`, pas de webhook | [0003](adr/0003-gradio-en-local-uniquement.md) |
| Courriel piégé (HTML, consigne au modèle) | texte échappé, HTML converti en texte, clause anti-injection, aucun outil côté modèle | [0007](adr/0007-courriels-traites-comme-non-fiables.md) |
| Données personnelles projetées | expéditeur jamais affiché, sélection par le présentateur | [0007](adr/0007-courriels-traites-comme-non-fiables.md) |
| Modification de la boîte | trois `GET` uniquement | [0005](adr/0005-agentmail-en-lecture-seule.md) |
