# 0001 · uv pour Python, l'environnement et les dépendances

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

La démo doit démarrer de façon identique sur le portable le jour J, sans surprise de version. Le projet d'origine n'avait ni environnement figé ni fichier de verrouillage.

## Décision

uv gère tout : version de Python (`.python-version` = `3.12`), environnement `.venv`, dépendances (`pyproject.toml`) et verrouillage (`uv.lock`, versionné). Le projet n'est pas un paquet (`[tool.uv] package = false`).

Démarrage, toujours le même :

```bash
uv sync --locked
uv run python app.py
```

`--locked` échoue si `uv.lock` ne correspond plus à `pyproject.toml`, au lieu de le modifier en silence.

## Alternatives écartées

- **pip + venv + requirements.txt** : pas de verrouillage complet des dépendances transitives, Python à installer à part.
- **Poetry** : plus lent, n'installe pas Python, outil supplémentaire.

## Conséquences

- Installation reproductible, vérifiée dans une copie propre (uv 0.13.5, Python 3.12.12).
- Toute modification de dépendance passe par `uv add` ou `uv lock`.
- uv est fourni par mise : dans un terminal neuf, il n'apparaît dans le `PATH` qu'après le premier prompt.
