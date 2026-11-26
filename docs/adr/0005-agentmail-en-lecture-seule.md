# 0005 · Boîte AgentMail dédiée, en lecture seule

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

Le public doit pouvoir écrire un vrai courriel pendant la présentation. Un compte AgentMail existe déjà pour un autre projet (Scout), dont les messages et la configuration ne doivent pas être touchés.

## Décision

- Une boîte **dédiée AI Coffee** et une clé **dédiée**, limitée si possible à cette boîte et aux droits `inbox_read` et `message_read`.
- `live_inbox.py` n'utilise que trois `GET` sur l'API v0 : la boîte, la liste des messages (50 par page, 5 pages au plus), un message.
- Les messages envoyés (`sent`) sont ignorés ; chaque message est gardé une seule fois, par `message_id`.
- Corps lu dans l'ordre `extracted_text` → `text` → `extracted_html` → `html` (HTML converti en texte brut).
- Chaque panne a son message en français : clé refusée (401/403), boîte introuvable (404), limite de requêtes (429), serveur (5xx), délai dépassé, pas d'Internet, configuration absente.
- `uv run python live_inbox.py` teste la connexion sans jamais afficher la clé.

## Alternatives écartées

- **Réutiliser la boîte de Scout** : mélange des données, risque d'afficher des messages réels.
- **Gmail / IMAP** : authentification plus lourde et compte personnel exposé.
- **Webhooks AgentMail** : exige une URL publique, contraire à [0003](0003-gradio-en-local-uniquement.md).

## Conséquences

- Le relevé est manuel (« Relever les nouveaux messages ») : le présentateur garde la main.
- Une panne réseau ne bloque que l'onglet direct ; la démo préparée reste utilisable sans redémarrer.
- Couvert par les tests `tests/test_live_inbox.py` (API simulée).
