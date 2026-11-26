# 0004 · Un classifieur partagé, sortie JSON et citation vérifiée

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

Les deux onglets doivent appliquer exactement la même règle. Un petit modèle peut répondre dans un format inattendu ou inventer une phrase pour justifier sa décision. Le public doit pouvoir vérifier chaque suggestion.

## Décision

- Une seule fonction `core.classify(subject, body, model)`, appelée par les deux onglets.
- Le prompt d'origine du projet est conservé, avec une clause anti-injection (voir [0007](0007-courriels-traites-comme-non-fiables.md)).
- Sortie forcée par un schéma JSON dans le champ `format` d'Ollama : `{"demande": bool, "citation": str}`.
- Pour une demande, `locate_quote` doit retrouver la citation **telle quelle** dans le corps ou l'objet. Seuls les espaces, les apostrophes droites ou typographiques et les guillemets autour sont tolérés. Sinon le message est marqué « ⚠️ À vérifier » et n'est pas compté comme trouvé.
- Deux types d'erreur : `ServiceError` (Ollama inutilisable, l'analyse s'arrête sans score) et `AnalysisError` (ce message seul est à revoir).
- Le modèle ne reçoit que `{"objet", "message"}` (corps tronqué à 4 000 caractères) : jamais l'identifiant, le corrigé ni l'expéditeur.

## Alternatives écartées

- **Un prompt différent par onglet** : comparaison faussée.
- **Analyse du texte libre du modèle** : fragile.
- **Prompt réécrit plus détaillé** : essayé, il a produit 3 fausses alertes (09, 15, 19) ; abandonné au profit du prompt d'origine.

## Conséquences

- Chaque suggestion affichée est prouvée par un extrait réel du courriel.
- Un score n'existe que pour une analyse complète des 20 messages ; une relance efface l'ancien.
- Couvert par les tests `tests/test_core.py`.
