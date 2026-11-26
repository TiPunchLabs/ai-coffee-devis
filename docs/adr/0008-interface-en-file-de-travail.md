# 0008 · Interface en file de travail (liste + détail)

- **Statut** : Accepté
- **Date** : 26/11/2026

## Contexte

La première interface empilait des tableaux (boîte de réception repliée, résultats du mot-clé, rappels suggérés, corrigé). Elle ne permettait pas de sélectionner un message. Sur téléphone, les tableaux étaient tronqués et l'onglet en direct passait par une liste déroulante et un bouton « Afficher ». Une personne qui découvre l'écran doit voir en cinq secondes quelles demandes traiter, ce que le client demande et quoi faire ensuite.

## Décision

- **Mise en page** : titre compact « Demandes de devis », puis une barre d'actions, avec à gauche la liste des messages et à droite le détail du message sélectionné. Les deux onglets suivent le même schéma.
- **Liste** : un `gr.HTML` affiche des boutons de ligne (numéro ou heure, objet, aperçu, statut). Un clic, ou `Tab` puis `Entrée`, envoie l'identifiant à Python via `trigger('select', {id})` dans `js_on_load` ; Python le lit dans `gr.EventData`. Le texte des courriels est échappé côté Python.
- **Statut lisible sans couleur** : « ● À rappeler », « ▲ À vérifier », « Pas une demande » et « Non analysé ». L'ambre est réservé aux deux premiers. L'en-tête de liste affiche des comptes calculés à partir des lignes affichées.
- **Détail** : il commence par « Ce que demande le client », c'est-à-dire la citation vérifiée, suivie de la prochaine étape, puis du courriel d'origine où cette citation est surlignée.
- **Actions** : « 2 · Analyser les 20 messages » est l'action principale de la démo préparée. Dans l'onglet en direct, « Analyser ce message avec le modèle local » n'apparaît qu'une fois un message sélectionné.
- **Thème** : `gr.themes.Base` avec un fond neutre, un seul accent indigo, des polices système (aucun téléchargement, la démo hors ligne reste possible) et une petite feuille CSS ciblée par `elem_id` et `elem_classes`.
- **Mobile** : la liste est limitée à 46 % de la hauteur avec un défilement interne. Après une sélection, la page défile jusqu'au détail, qui commence par un lien « ← Retour à la liste ».

## Alternatives écartées

- **`gr.Dataframe` avec `.select`** : colonnes tronquées sur mobile, pas de badge de statut, sélection peu visible.
- **`gr.Radio` stylé** : libellés en texte seul, impossible d'y afficher un statut coloré et un aperçu.
- **Extraire équipement, quantité, dates et lieu** : il faudrait un second appel au modèle et modifier le prompt validé (4/4, 0 fausse alerte). Écarté pour la démo : la citation exacte tient lieu de résumé de la demande.
- **Afficher l'expéditeur dans la liste** : contraire à [0007](0007-courriels-traites-comme-non-fiables.md). Le corpus préparé n'a d'ailleurs pas d'expéditeur.

## Conséquences

- Les règles métier sont inchangées : même classifieur, corrigé caché jusqu'au clic, score calculé seulement sur une analyse complète, relance qui efface l'ancien score.
- Les libellés « 2 · Lancer l’analyse locale » et « Afficher ce message » ont disparu. Le README et `docs/AGENTMAIL.md` sont à jour.
- Le comportement de `trigger`/`js_on_load` dépend de Gradio 6 : à revérifier lors d'une montée de version.
