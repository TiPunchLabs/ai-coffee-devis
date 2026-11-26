# 0006 · Secrets via direnv et pass plutôt qu'un fichier `.env`

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

L'onglet direct a besoin de `AGENTMAIL_API_KEY` et `AGENTMAIL_INBOX_ID`. Une première version utilisait un fichier `.env` (ignoré par git) chargé par python-dotenv, avec un `.env.example`. L'auteur gère les secrets de tous ses projets avec `pass` et direnv.

## Décision

- Les valeurs vivent dans `pass` : `agentmail/ai-coffee-api-key` et `agentmail/ai-coffee-inbox-id`.
- Un fichier `.envrc` versionné, **sans aucun secret**, les exporte :

```bash
export AGENTMAIL_API_KEY=$(pass agentmail/ai-coffee-api-key)
export AGENTMAIL_INBOX_ID=$(pass agentmail/ai-coffee-inbox-id)
```

- `direnv allow` une fois, puis à chaque modification du fichier.
- python-dotenv a été retiré des dépendances et `.env.example` mis à la corbeille.

## Alternatives écartées

- **Fichier `.env`** : secret en clair sur le disque, risque de copie ou de commit.
- **Saisie de la clé dans l'interface** : visible à l'écran pendant une projection.

## Conséquences

- Aucun secret en clair dans le projet.
- L'application lit les variables **au démarrage** : il faut la lancer depuis un terminal où direnv est chargé (ou avec `direnv exec . uv run python app.py`) et la redémarrer après une correction dans `pass`.
- Sans ces variables, seule la démo préparée fonctionne, avec un message clair dans l'onglet direct.
