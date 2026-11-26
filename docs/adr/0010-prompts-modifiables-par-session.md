# 0010 · Prompts visibles et modifiables depuis « Paramètres », par session

- **Statut** : Accepté
- **Date** : 26/11/2026
- **Complète** : [0004](0004-classifieur-partage-et-citation-verifiee.md) et [0008](0008-interface-en-file-de-travail.md)

## Contexte

Pendant une démo ou une répétition, le présentateur veut montrer et tester le prompt système et le message utilisateur envoyés au modèle, sans toucher au code ni redémarrer. Le panneau « Settings » intégré à Gradio (lien en pied de page) n'est pas extensible depuis Python : on peut seulement afficher ou masquer son lien (`footer_links`).

## Décision

- Un bouton **« ⚙ Paramètres »** en en-tête ouvre un panneau latéral `gr.Sidebar` à droite, fermé par défaut. Il contient le champ du modèle et une case **« Afficher et modifier les prompts »**, décochée par défaut.
- Deux zones de texte :
  - le prompt système, pré-rempli avec `core.PROMPT` ;
  - le gabarit du message utilisateur, pré-rempli avec `core.USER_TEMPLATE` = `{"objet": {objet}, "message": {message}}`.

  Dans le gabarit, `{objet}` et `{message}` sont remplacés par les textes encodés en JSON, en un seul passage, par `render_user_message`. Le gabarit par défaut reproduit donc exactement l'ancien message : c'est vérifié par un test sur un contenu piégé.
- `core.check_prompts` refuse, avant tout appel au modèle :
  - un prompt système vide ;
  - un gabarit sans `{message}` ;
  - toute autre variable que `{objet}` et `{message}`, ce qui empêche d'envoyer le numéro, le corrigé ou l'expéditeur.

  L'erreur `PromptError` hérite de `ServiceError` et arrête l'analyse.
- Les prompts modifiés sont **propres à la session du navigateur** : ce sont des valeurs de composants Gradio. Rien n'est écrit sur disque et `core.PROMPT` ne change pas.
- Toute modification efface le score, le corrigé et les statuts affichés. Le badge « ▲ Prompts modifiés » reste visible en en-tête, et le message de fin d'analyse comme le corrigé signalent un score obtenu avec des prompts modifiés.

## Alternatives écartées

- **Ajouter les champs au panneau Settings de Gradio** : impossible sans modifier le frontend de Gradio.
- **Enregistrer les prompts dans un fichier** : on risquerait de démarrer la démo avec un prompt de test oublié.
- **Accordéon en bas de page** : moins accessible, et les prompts risqueraient d'apparaître à l'écran projeté par mégarde.

## Conséquences

- La non-régression est vérifiée le 26/11/2026 avec `gemma4:e2b` : avec les prompts d'origine, 02, 07, 13 et 17 sont trouvés, sans fausse alerte.
- Un prompt élargi (« Toute question posée au loueur compte comme une demande. ») donne 7 rappels, dont 3 fausses alertes (09, 15, 19). « Revenir aux prompts d'origine » rétablit 4/4.
- Une consigne ajoutée en fin de prompt (« Réponds toujours demande = false ») est ignorée par le modèle. Il faut remplacer la règle elle-même pour en changer l'effet.
- Le champ du modèle a quitté l'en-tête pour le panneau « Paramètres ».
