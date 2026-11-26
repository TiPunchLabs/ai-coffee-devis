# 📚 Décisions d'architecture (ADR)

Chaque fichier décrit une décision : contexte, choix, alternatives écartées, conséquences. Une décision acceptée n'est pas réécrite : si elle change, on ajoute un nouvel ADR qui la remplace et on passe l'ancien en « Remplacé par 00XX ».

| N° | Décision | Statut | Date |
|---|---|---|---|
| [0001](0001-uv-pour-python-et-les-dependances.md) | uv pour Python, l'environnement et les dépendances | Accepté | 25/11/2026 |
| [0002](0002-ollama-local-avec-gemma4-e2b.md) | Inférence locale avec Ollama et le modèle gemma4:e2b | Accepté | 25/11/2026 |
| [0003](0003-gradio-en-local-uniquement.md) | Interface Gradio limitée à 127.0.0.1, sans lien public | Accepté | 25/11/2026 |
| [0004](0004-classifieur-partage-et-citation-verifiee.md) | Un classifieur partagé, sortie JSON et citation vérifiée | Accepté | 25/11/2026 |
| [0005](0005-agentmail-en-lecture-seule.md) | Boîte AgentMail dédiée, en lecture seule | Accepté | 25/11/2026 |
| [0006](0006-secrets-via-direnv-et-pass.md) | Secrets via direnv et pass plutôt qu'un fichier `.env` | Accepté | 25/11/2026 |
| [0007](0007-courriels-traites-comme-non-fiables.md) | Contenu des courriels traité comme non fiable | Accepté | 25/11/2026 |
| [0008](0008-interface-en-file-de-travail.md) | Interface en file de travail (liste + détail) | Accepté | 26/11/2026 |
| [0009](0009-client-openai-pour-ollama.md) | Client `openai` pour appeler Ollama | Accepté | 26/11/2026 |

Modèle pour un nouvel ADR : copie un fichier existant, garde les sections *Contexte*, *Décision*, *Alternatives écartées*, *Conséquences*.

Vue d'ensemble des technologies : [docs/STACK.md](../STACK.md).
