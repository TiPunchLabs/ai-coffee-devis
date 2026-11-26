# 0003 · Interface Gradio limitée à 127.0.0.1, sans lien public

- **Statut** : Accepté
- **Date** : 25/11/2026

## Contexte

Il faut une interface projetable, en français, avec deux onglets, une progression visible pendant l'analyse et un bouton d'arrêt. Le portable est sur un réseau public et l'application détient une clé AgentMail.

## Décision

Gradio 6.32.0, lancé avec `server_name="127.0.0.1"`, `share=False`, port `GRADIO_SERVER_PORT` (7860 par défaut), télémétrie coupée (`GRADIO_ANALYTICS_ENABLED=False`). La progression utilise un générateur Gradio ; « Arrêter l'analyse » annule l'événement en cours.

## Alternatives écartées

- **FastAPI + front React/Vue** : beaucoup plus de code pour une démo de 5 minutes.
- **Streamlit** : réexécute tout le script à chaque clic, moins adapté à une analyse longue interruptible.
- **Lien public Gradio (`share=True`)** : exposerait l'application, et donc la boîte AgentMail, sur Internet.

## Conséquences

- Seul ce portable peut ouvrir http://127.0.0.1:7860 ; le public ne fait qu'envoyer des courriels.
- Un seul processus : l'arrêter vide la liste des messages relevés (ils restent dans AgentMail).
- Arrêt et libération du port : [README, section 3.4](../../README.md#34-arrêter-lapplication).
