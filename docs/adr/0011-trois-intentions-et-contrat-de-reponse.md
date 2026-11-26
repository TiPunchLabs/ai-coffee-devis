# 0011 · Trois intentions et contrat de réponse à trois champs

- **Statut** : Accepté
- **Date** : 26/11/2026
- **Remplace en partie** : [0004](0004-classifieur-partage-et-citation-verifiee.md), pour le format de réponse et le prompt par défaut

## Contexte

Le courriel « Devis D-402 : changement de date » demande de décaler la livraison d'un devis signé. L'ancien contrat ne connaissait que `demande` (booléen) et `citation`, et le prompt excluait le « suivi de location déjà conclue ». Une modification n'avait donc pas de place : selon le texte reçu, elle sortait en nouvelle demande, ou en « Pas une demande » avec « Rien de nouveau à proposer ».

Le cas observé dans l'interface avait en plus un corps de courriel contaminé. Le bloc copié depuis `docs/mails_exemple.md` contenait le commentaire d'évaluation (« Extrait retenu : … La règle exclut le suivi d'une location déjà conclue… »), qui a été envoyé au modèle comme texte du client.

## Décision

- **Trois intentions** :
  - `nouvelle_location` : seule comptée comme nouvelle demande, et seule utilisée pour le score de la démo préparée ;
  - `modification_location` ;
  - `autre`.
- **Réponse attendue** : exactement `{"demande", "type_demande", "citation"}`. Combinaisons autorisées :
  - `nouvelle_location` ou `modification_location` avec `demande: true` et une citation non vide ;
  - `autre` avec `demande: false` et `citation: ""`.
- **Prompt système** : nouveau texte fourni par l'auteur, avec trois exemples génériques. Le cas D-402 n'y figure pas, pour rester un cas de non-régression jamais montré au modèle. Le message utilisateur ne contient que l'objet et le corps.
- **Schéma imposé au modèle** : `core.response_schema(body)` est calculé pour chaque courriel. C'est un `oneOf` à deux branches, catégorie en premier, ce qui rend les combinaisons contradictoires impossibles à générer. Dans la branche « demande », la `citation` est un `enum` des extraits réels du corps (chaque phrase, et sa fin après `,` `;` `:`), pris dans le même corps tronqué que celui envoyé au modèle.
  - Pourquoi : avec un schéma simple, `gemma4:e2b` classait bien D-402 en modification, mais réécrivait « pouvez-vous » en « pourriez-vous », probablement par imitation de l'exemple 2. Il renvoyait aussi des incohérences : `autre` avec une citation, `autre` avec `demande: true`.
- **Validation côté application** (`parse_verdict`) : elle revérifie tout, à savoir les champs, l'énumération, le vrai booléen, la cohérence, et une citation retrouvée dans le corps seulement. Accents, ponctuation et casse sont conservés ; seuls les espaces, le type d'apostrophe et les guillemets autour sont tolérés. Tout écart donne « Analyse à vérifier », distinct de « Hors périmètre ».
- **Interface** :

  | Catégorie | Libellé | Prochaine étape suggérée |
  |---|---|---|
  | `nouvelle_location` | « ● Nouvelle demande de location » | « Vérifier la disponibilité du matériel et préparer une réponse. » |
  | `modification_location` | « ◆ Modification de location » | « Vérifier si la modification est possible et répondre au client. » |
  | `autre` | « Hors périmètre » | « Aucune location à préparer ni à modifier. Si le courriel pose une question, y répondre normalement. » |

  Les compteurs sont « N à traiter » (nouvelles demandes et modifications) et « M nouvelle(s) demande(s) de location ». Ils sont calculés à partir d'un résultat par message, donc ré-analyser un message ne le compte qu'une fois.
- **Résultats périmés** : chaque résultat stocké porte `contract: 2`. Un résultat d'un autre format, comme l'ancien `demande: false`, est ignoré et le message redevient « Non analysé ». Les analyses ne sont jamais enregistrées sur disque : elles vivent dans la session Gradio et disparaissent au redémarrage.

## Alternatives écartées

- **Second appel au modèle ou classifieur par mots-clés** : exclus par le besoin.
- **Filtrer « Extrait retenu », « La règle… » dans les courriels** : ce serait supprimer du texte client. Le correctif consiste à séparer données et attentes (tests, `docs/AGENTMAIL.md`).
- **Tolérer « pourriez-vous » pour « pouvez-vous »** : une citation doit être le texte du client, pas une reformulation.

## Conséquences

Mesures du 26/11/2026 avec `gemma4:e2b` :
- **Courriels d'acceptation** : 7/7 conformes, trois fois de suite, modèle chaud comme froid (`OLLAMA_LIVE=1 uv run pytest tests/test_intents_live.py`). Pour D-402, la catégorie est `modification_location` et l'extrait est « pour le devis D-402 déjà signé, pouvez-vous décaler la livraison des chapiteaux du 5 au 6 décembre ? ».
- **Démo préparée** : 02, 07, 13, 17 en nouvelle demande, 16 hors périmètre, 0 fausse alerte, aucune modification.
- **Forme des extraits** : une citation est toujours une phrase entière ou une fin de phrase du corps. Elle ne peut pas commencer au milieu d'une proposition.
