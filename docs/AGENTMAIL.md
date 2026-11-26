# ✉️ AgentMail · Configurer et tester la boîte dédiée AI Coffee

> **Prérequis** : le projet est installé et la « Démo préparée » fonctionne (voir [README](../README.md), section 3.1). Un compte AgentMail existe déjà (celui de Scout). Durée : 10 à 15 minutes, avec Internet.

Le principe : AgentMail **héberge** les courriels envoyés par le public ; l'application les **lit** (lecture seule) puis les fait classer **sur le portable** par Ollama. La boîte et la clé AI Coffee sont **distinctes** de celles de Scout : ne réutilise ni l'adresse, ni la clé, ni le fichier de configuration de Scout.

```
Public ──courriel──► boîte AgentMail AI Coffee ──(Internet, GET seulement)──► app.py ──► Ollama local
```

Documentation officielle utilisée :

- Obtenir une clé : https://docs.agentmail.to/knowledge-base/getting-api-key
- Boîtes et clés limitées à une boîte : https://docs.agentmail.to/inboxes
- Permissions des clés : https://docs.agentmail.to/permissions
- Lister les messages : https://docs.agentmail.to/api-reference/inboxes/messages/list
- Lire un message : https://docs.agentmail.to/api-reference/inboxes/messages/get

------

## 1. Se connecter et créer (ou choisir) la boîte dédiée

1. Ouvre la console : https://console.agentmail.to et connecte-toi avec le compte existant.
2. Dans la liste des boîtes (*Inboxes*), crée une nouvelle boîte réservée à AI Coffee, par exemple avec le nom d'utilisateur `ai-coffee-gwada` sur le domaine par défaut `agentmail.to`. Nom d'affichage suggéré : `AI Coffee démo`.
   - Le nom d'utilisateur est la partie avant `@` ; s'il est laissé vide, AgentMail en génère un au hasard. Le domaine par défaut est `agentmail.to`.

> 💡 **Déjà fait ?** Si une boîte AI Coffee existe déjà, ne la recrée pas : sélectionne-la et passe à l'étape 2. **N'utilise jamais la boîte de Scout.**

> ⚠️ **Note** : les libellés exacts des boutons de la console n'ont pas pu être vérifiés dans la documentation (seule la rubrique **API Keys** et le bouton **Create New API Key** y sont décrits). Le test de l'étape 4 confirme de toute façon que la bonne boîte est utilisée.

## 2. L'adresse à montrer et la valeur de `AGENTMAIL_INBOX_ID`

Dans AgentMail, **l'identifiant d'une boîte (`inbox_id`) est son adresse e-mail complète**. La documentation l'écrit ainsi : `inbox_id="agent@yourdomain.com"`, et la réponse « Get Inbox » renvoie `inbox_id` et `email`.

Donc, pour une boîte `ai-coffee-gwada@agentmail.to` :

| Usage | Valeur |
|---|---|
| Adresse affichée au public | `ai-coffee-gwada@agentmail.to` |
| `AGENTMAIL_INBOX_ID` (entrée `pass agentmail/ai-coffee-inbox-id`) | `ai-coffee-gwada@agentmail.to` (identique) |

L'onglet « En direct avec AgentMail » affiche l'adresse que **AgentMail confirme** (champ `email` de la boîte) après le premier clic sur « Relever les nouveaux messages ».

## 3. Clé API, `pass` et `.envrc`

Comme dans tes autres projets, les valeurs ne sont **jamais écrites sur le disque en clair** : elles vivent dans `pass`, et le fichier `.envrc` du projet (versionné, sans secret) les exporte via direnv quand tu entres dans le dossier.

```bash
# .envrc (déjà présent dans le projet)
export AGENTMAIL_API_KEY=$(pass agentmail/ai-coffee-api-key)
export AGENTMAIL_INBOX_ID=$(pass agentmail/ai-coffee-inbox-id)
```

1. Dans la console, rubrique **API Keys**, clique **Create New API Key**. Nom suggéré : `ai-coffee-demo-lecture`.
   - Si la console le permet, limite la clé à la boîte AI Coffee (clé « inbox-scoped ») et aux droits de lecture `inbox_read` et `message_read`. L'application n'utilise que trois lectures : la boîte, la liste des messages, un message.
   - **Déjà une clé AI Coffee ?** Réutilise-la. **Ne copie pas la clé de Scout** (ni son entrée `pass`).
2. Copie la clé **immédiatement** : elle n'est affichée qu'une fois.
3. Range les deux valeurs dans `pass`. `pass insert` demande la valeur de façon masquée : elle n'apparaît ni à l'écran ni dans l'historique du shell.

```bash
pass insert agentmail/ai-coffee-api-key      # colle la clé AI Coffee, Entrée, puis confirme
pass insert agentmail/ai-coffee-inbox-id     # saisis l'adresse complète, ex. ai-coffee-gwada@agentmail.to
```

> 💡 **Déjà fait ?** `pass ls agentmail` affiche les entrées existantes ; saute cette étape si les deux sont là. Pour corriger une valeur : `pass edit agentmail/ai-coffee-inbox-id` (ou `pass insert -f …`).

4. Autorise le `.envrc` du projet (une seule fois, et après chaque modification du fichier) :

```bash
cd ~/Workspace/102-ai-coffee/ai-coffee-devis
direnv allow
```

Succès : direnv affiche `direnv: export +AGENTMAIL_API_KEY +AGENTMAIL_INBOX_ID` (gpg peut demander ta phrase de passe). Vérification sans rien révéler de la clé :

```bash
[ -n "$AGENTMAIL_API_KEY" ] && echo "clé chargée" || echo "clé ABSENTE"
echo "$AGENTMAIL_INBOX_ID"
```

> 🔐 **Sécurité** : aucune valeur secrète dans le projet ; `.envrc` ne contient que les noms des entrées `pass`. Ne colle jamais la clé dans une conversation, une capture d'écran ou une diapositive. L'application ne l'affiche nulle part ; le test ci-dessous écrit seulement « présente (masquée) ».

> ⚠️ **Warning** : l'application lit ces variables **au démarrage**. Lance toujours `uv run python app.py` depuis un terminal ouvert dans le projet (direnv chargé). Après une correction dans `pass`, refais `direnv reload`, puis redémarre l'application (`Ctrl+C`, puis `uv run python app.py` ; si le terminal d'origine est fermé, voir [README, section 3.4](../README.md#34-arrêter-lapplication)). La démo préparée fonctionne même si `pass` ou direnv ne fournissent rien.

## 4. Test de connexion (sans Gradio)

Toujours à la racine du projet (direnv chargé) :

```bash
uv run python live_inbox.py
```

Lecture des résultats :

| Sortie | Signification |
|---|---|
| `CONNEXION OK : boîte confirmée par AgentMail = ai-coffee-gwada@agentmail.to` puis `Messages reçus … : 0. Boîte vide : aucun message reçu pour l’instant.` | **Succès**, boîte vide : la clé est acceptée et la boîte existe. |
| `CONNEXION OK …` puis `Messages reçus … : N.` | Succès, N messages déjà présents. |
| `ÉCHEC : Clé AgentMail refusée.` | La requête est **rejetée** (HTTP 401/403) : clé fausse, révoquée ou sans droit sur cette boîte. |
| `ÉCHEC : Boîte AgentMail introuvable pour cette clé.` | `AGENTMAIL_INBOX_ID` faux (entrée `pass agentmail/ai-coffee-inbox-id`), ou clé limitée à une autre boîte (celle de Scout ?). |
| `ÉCHEC : Configuration AgentMail absente (…)` | entrée `pass` manquante, `direnv allow` pas fait, ou commande lancée hors du dossier du projet. |
| `ÉCHEC : Pas d’accès Internet vers AgentMail.` | Réseau indisponible. |

Vérifie que l'adresse confirmée est bien celle d'AI Coffee, **pas celle de Scout**.

## 5. Premier message en direct

1. Depuis le dossier du projet (direnv chargé), lance l'application : `uv run python app.py`, ouvre http://127.0.0.1:7860.
2. Onglet **« En direct avec AgentMail »** : clique **« Relever les nouveaux messages »**. L'adresse en titre doit être celle d'AI Coffee ; le statut indique « Boîte vide » ou le nombre de messages.
3. Depuis **une autre adresse** (ton Gmail personnel, par exemple), envoie l'un des messages de l'étape 6 à cette adresse.
4. Attends 20 à 30 secondes, clique à nouveau **« Relever les nouveaux messages »** : « 1 nouveau(x) message(s) relevé(s) ».
5. Clique-le dans la liste de gauche (heure · objet · statut) : l'objet et le texte s'affichent à droite, sans l'expéditeur. Le bouton **« Analyser ce message avec le modèle local »** apparaît au-dessus.
6. Clique **« Analyser ce message avec le modèle local »** : la ligne prend son statut (« ● Nouvelle demande de location », « ◆ Modification de location » ou « Hors périmètre ») ; pour les deux premiers, « Ce que demande le client » affiche l'extrait exact, surligné dans le courriel, et la prochaine étape suggérée. L'en-tête de liste compte les messages « à traiter » et, à part, les nouvelles demandes de location.
7. Clique encore **« Relever les nouveaux messages »** : « Aucun nouveau message (1 déjà relevé(s)) » ; le message reste une seule fois dans la liste et reste sélectionnable. L'onglet « Démo préparée » et son score ne changent pas.

## 6. Trois messages de répétition (fictifs)

**Message A · nouvelle demande, sans le mot « devis »** — verdict attendu : *Nouvelle demande de location*

```text
Objet : Mariage à Saint-François
Bonjour, nous nous marions le 19 décembre à Saint-François. Auriez-vous 80 chaises blanches et deux tentes de 6 mètres ? Merci de me dire si c'est possible.
```

**Message B · suivi de paiement, avec le mot « devis »** — verdict attendu : *Hors périmètre*

```text
Objet : Règlement du devis D-311
Bonjour, je vous confirme le virement du solde pour le devis D-311 accepté la semaine dernière. Merci de m'envoyer la facture.
```

**Message C · modification d'un devis signé** — verdict attendu : *Modification de location*

```text
Objet : Devis D-402 : changement de date
Bonjour, pour le devis D-402 déjà signé, pouvez-vous décaler la livraison des chapiteaux du 5 au 6 décembre ? Le reste ne change pas.
```

Ne copie que le contenu des blocs `text` : le verdict attendu et tout commentaire restent hors du courriel, sinon ils sont envoyés au modèle comme texte du client.

Lors de la répétition du 26/11/2026 (appel direct du classifieur, `gemma4:e2b`) : A → nouvelle demande (extrait : « Auriez-vous 80 chaises blanches et deux tentes de 6 mètres ? »), B → hors périmètre, C → modification (extrait : « pour le devis D-402 déjà signé, pouvez-vous décaler la livraison des chapiteaux du 5 au 6 décembre ? »).

### Consigne à afficher ou dire au public

> Écrivez à l'adresse affichée un **message fictif** : une demande à un loueur de matériel… ou un piège. **Pas de vraie information personnelle, pas de signature, pas de numéro de téléphone.** Seuls l'objet et le texte seront projetés.

## 7. Diagnostic

| Symptôme dans l'onglet en direct | Cause probable | Action |
|---|---|---|
| L'adresse affichée n'est pas celle d'AI Coffee | mauvaise valeur dans `pass` | `pass edit agentmail/ai-coffee-inbox-id`, `direnv reload`, redémarre l'application ; refais l'étape 4 |
| « Boîte AgentMail introuvable pour cette clé » | mauvaise boîte, ou clé limitée à une autre boîte | vérifie l'adresse exacte dans la console ; utilise la clé AI Coffee |
| « Clé AgentMail refusée » | clé fausse, révoquée, ou sans droit de lecture | crée une nouvelle clé (étape 3), `pass insert -f agentmail/ai-coffee-api-key`, `direnv reload`, redémarre l'application |
| « Configuration AgentMail absente » | application lancée sans direnv, ou `pass` verrouillé | `cd` dans le projet, `direnv allow`, déverrouille gpg si demandé, redémarre l'application |
| « Aucun nouveau message (N déjà relevé(s)) » | le message est déjà dans la liste, ou n'est pas encore arrivé | regarde la liste de gauche : il y est déjà ; sinon attends 20 s et reclique. Vérifie que l'expéditeur a écrit à la bonne adresse |
| « Boîte vide » | aucun message reçu | vérifie l'adresse utilisée par l'expéditeur ; regarde la boîte dans la console AgentMail |
| « sans texte lisible » / « Ce message n’a pas de texte lisible » | image ou pièce jointe seule | demande d'écrire directement dans le corps du courriel |
| « Pas d’accès Internet vers AgentMail » ou « délai dépassé » | Wi-Fi de la salle | partage de connexion du téléphone, ou reviens à l'onglet « Démo préparée » (aucun redémarrage) |
| « AgentMail limite les requêtes » | trop de clics rapprochés | attends quelques secondes |
| « Ollama ne répond pas … » lors de l'analyse | service local arrêté | `sudo systemctl start ollama` |

Les messages relevés restent en mémoire tant que l'application tourne (même après un rechargement de la page). Un redémarrage de `app.py` vide la liste ; un nouveau clic sur « Relever » les récupère à nouveau depuis AgentMail.
