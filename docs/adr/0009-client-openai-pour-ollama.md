# 0009 · Client `openai` pour appeler Ollama

- **Statut** : Accepté
- **Date** : 26/11/2026
- **Complète** : [0002](0002-ollama-local-avec-gemma4-e2b.md) et [0004](0004-classifieur-partage-et-citation-verifiee.md), sans changer de modèle ni de règle

## Contexte

Le classifieur appelait directement l'API native d'Ollama (`POST /api/chat`) avec `httpx`. L'auteur préfère le package Python officiel `openai`, qu'il utilise ailleurs et qui permettrait de pointer plus tard vers un autre serveur compatible OpenAI sans réécrire le code.

## Décision

- `core.get_client()` crée `OpenAI(base_url=f"{OLLAMA_URL}/v1", api_key="ollama", timeout=180, max_retries=0)`. La clé est factice : Ollama local ne l'exige pas.
- `core.classify` appelle `chat.completions.create` avec :
  - `temperature=0` ;
  - `reasoning_effort="none"`, l'équivalent de `think: false` ;
  - `response_format` de type `json_schema`, avec le même schéma `{demande, citation}` ;
  - `extra_body={"keep_alive": "30m"}`, une extension d'Ollama absente de la liste des champs compatibles, mais prise en compte : vérifié avec `ollama ps`, qui affiche « 29 minutes from now ».
- `max_retries=0` : en cas de panne, l'erreur s'affiche tout de suite au lieu de trois tentatives silencieuses.
- Les exceptions typées du client sont traduites dans les mêmes messages français qu'avant :

  | Exception | Erreur affichée |
  |---|---|
  | `APIConnectionError` | Ollama ne répond pas |
  | `APITimeoutError` | délai dépassé |
  | `NotFoundError` | modèle introuvable |
  | `APIStatusError` | code HTTP |

- La version est `openai>=3.49.0,<3.50` : la plus récente publiée depuis au moins deux semaines au 26/11/2026.
- `httpx` reste une dépendance directe, pour AgentMail et pour les tests.

## Alternatives écartées

- **Garder `httpx` et `/api/chat`** : fonctionnel, mais ce n'est pas l'outil que préfère l'auteur.
- **Package `ollama`** : propre à Ollama, il n'apporte pas la portabilité vers d'autres serveurs compatibles OpenAI.

## Conséquences

- Les résultats sont identiques. Mesures du 26/11/2026 avec `gemma4:e2b`, sur deux analyses complètes des 20 messages : 02, 07, 13, 17 trouvés, 0 fausse alerte, 0 erreur, environ 2,7 s, avec les mêmes extraits qu'avant.
- Les tests simulent Ollama au niveau HTTP (`OpenAI(http_client=httpx.Client(transport=MockTransport))`). Ils couvrent donc les vraies exceptions du client et vérifient les réglages envoyés.
- Une dépendance de plus (`openai`, plus `jiter` et `sniffio` ; les autres dépendances du client étaient déjà présentes), téléchargée une seule fois. La démo préparée fonctionne toujours hors ligne.
