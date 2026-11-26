# 0002 · Inférence locale avec Ollama et le modèle gemma4:e2b

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

Le message de la démo est qu'un modèle tournant **sur le portable**, sans Internet, peut trier une boîte mail. Le Wi-Fi de la salle n'est pas garanti. Le modèle doit comprendre le français, produire une sortie structurée et répondre assez vite pour tenir dans un créneau de 5 minutes. Seuls les modèles déjà installés étaient envisagés.

## Décision

Ollama (0.40.16) sur `127.0.0.1:11434`, modèle par défaut `gemma4:e2b`, modifiable par `OLLAMA_MODEL`. Appel `/api/chat` avec `temperature: 0`, `think: false`, `keep_alive: "30m"`.

Mesures sur les 20 courriels du corpus (corrigé : 02, 07, 13, 17) :

| Modèle | Trouvées | Fausses alertes | Citations invalides | Durée (20 messages) |
|---|---|---|---|---|
| **gemma4:e2b** | **4/4** | **0** | **0** | **~3 s à chaud, 13–15 s à froid** |
| deepseek-r1:8b | 4/4 | 0 | 0 | ~233 s |
| llama3.2:3b | — | 5 | 1 | ~12 s |
| phi3 | — | 7 | 3 | ~18 s |

## Alternatives écartées

- **API distante (Claude, GPT…)** : contredit le message « local », dépend du réseau, envoie les courriels hors du portable.
- **deepseek-r1:8b** : aussi juste, mais près de 4 minutes, incompatible avec le script.
- **llama3.2:3b, phi3** : trop de fausses alertes et de citations inventées.

## Conséquences

- La démo préparée fonctionne sans Internet (vérifié avec une isolation réseau complète).
- Faire une analyse complète dans les 30 minutes avant de passer, pour que le modèle soit déjà chargé.
- Résultat mesuré sur 20 exemples fictifs seulement : ce n'est pas une preuve de performance en conditions réelles.
