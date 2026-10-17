# Publier vers ntfy depuis une domotique

Le paquet `ntfy.yaml` fait publier **l'ESP** directement. Une domotique peut aussi **émettre** vers ntfy, par exemple pour :
- envoyer aux voisins un message construit à partir des entités du compteur (Home Assistant) ;
- qu'un voisin équipé de **sa propre** domotique (Jeedom, Domoticz, openHAB…) publie ses alertes ou réponde sur un sujet commun ;
- garder un seul canal de notification pour toute la maison, quel que soit le système qui envoie.

Le principe est le même partout : une requête HTTP `POST` vers le serveur ntfy ([documentation de publication](https://docs.ntfy.sh/publish/)). Deux formes au choix :

| Forme | Adresse | Corps | Options |
|---|---|---|---|
| Simple | `https://ntfy.sh/<sujet>` | le texte du message | en-têtes `Title`, `Priority`, `Tags` |
| JSON | `https://ntfy.sh/` (racine, pas le sujet) | `{"topic": …, "title": …, "message": …, "priority": 1-5, "tags": […]}` | dans le JSON |

La forme JSON évite les soucis d'accents dans les en-têtes HTTP. ntfy accepte l'UTF-8 dans les en-têtes, mais certaines bibliothèques le gèrent mal. Sur un serveur protégé, ajoute l'en-tête `Authorization: Bearer tk_…` (jeton d'accès).

Exemples avec un sujet fictif : remplace `eau-3f9c2a7d1b6e4f0a8c5d2e71` par le tien.

---

## Home Assistant

### Avec l'intégration ntfy (recommandé)

Home Assistant a une [intégration ntfy officielle](https://www.home-assistant.io/integrations/ntfy/) :

1. Paramètres → Appareils et services → **Ajouter une intégration** → **ntfy**.
2. Adresse du serveur : `https://ntfy.sh` (par défaut) ou celle de ton serveur. Nom d'utilisateur et mot de passe seulement si le serveur est protégé : HA crée lui-même un jeton d'accès.
3. **Ajouter un sujet** (« Add topic ») : saisis un sujet existant, ou laisse HA en générer un au hasard. Recommence pour chaque sujet (un par voisin).

Pour chaque sujet, HA crée :
- une entité **`notify.<sujet>`** pour **envoyer** ;
- une entité **`event.<sujet>`** qui **reçoit** en temps réel les messages du sujet, avec titre, tags, priorité… dans ses attributs. Un voisin équipé de HA peut s'en servir pour déclencher ses propres automatisations à partir du bilan envoyé par l'ESP.

Envoi simple :

```yaml
action: notify.send_message
target:
  entity_id: notify.eau_3f9c2a7d1b6e4f0a8c5d2e71
data:
  title: "Eau : bilan du jour"
  message: "Conso aujourd'hui : 123 L"
```

Envoi avec priorité et émojis (action `ntfy.publish`) :

```yaml
action: ntfy.publish
target:
  entity_id: notify.eau_3f9c2a7d1b6e4f0a8c5d2e71
data:
  title: "Fuite confirmée"
  message: "Consommation continue depuis 24 h."
  priority: "5"            # 1 = min … 5 = max
  tags: ["rotating_light", "droplet"]
```

Exemple complet, une automatisation qui envoie chaque soir au voisin 1 le bilan de son compteur à partir des entités ESPHome : [`exemples/home-assistant.yaml`](../exemples/home-assistant.yaml).

### Sans l'intégration (`rest_command`)

```yaml
# configuration.yaml
rest_command:
  ntfy:
    url: "https://ntfy.sh/"
    method: post
    content_type: "application/json"
    # headers:
    #   Authorization: !secret ntfy_bearer      # "Bearer tk_…" si serveur protégé
    payload: >-
      {{ {"topic": topic, "title": title, "message": message,
          "priority": priority | default(3) | int, "tags": tags | default([])} | to_json }}
```

```yaml
action: rest_command.ntfy
data:
  topic: eau-3f9c2a7d1b6e4f0a8c5d2e71
  title: "Débit anormal"
  message: "{{ states('sensor.compteur_eau_lora_debit_estime') }} L/h"
  priority: 5
  tags: ["warning", "droplet"]
```

---

## Jeedom

### Avec le plugin Ntfy (Lunarok, gratuit)

Le plugin **Ntfy** se trouve dans le Market, catégorie Communication ([documentation](https://lunarok.github.io/jeedom_docs/plugins/ntfy/)).

1. Plugins → Gestion des plugins → Market → installe **Ntfy**, puis active-le.
2. Plugins → Communication → **Ntfy** → **Ajouter** un équipement par sujet.
3. Champ **URL** = adresse complète du sujet : `https://ntfy.sh/eau-3f9c2a7d1b6e4f0a8c5d2e71`, ou `https://ntfy.exemple.fr/eau-…` pour un serveur privé.
4. Champs **user / password** uniquement si ton serveur est protégé.

L'équipement crée une seule commande, **Envoi de message**. Le **message** est le texte de la notification. Le champ **titre** sert à passer les options ntfy, séparées par des points-virgules :

```
Title: Fuite confirmée;Priority: urgent;Tags: rotating_light,droplet
```

Utilisation dans un **scénario** (bloc Action → commande de l'équipement Ntfy) :
- Titre : `Title: Eau : bilan du jour;Priority: low;Tags: droplet`
- Message : `Conso aujourd'hui : #[Maison][Compteur eau][Conso aujourd'hui]# L`

Remplace `#[Maison][Compteur eau][Conso aujourd'hui]#` par la commande info de ton propre compteur dans Jeedom.

Le plugin communautaire **ntfybridge** permet aussi des échanges dans les deux sens : il reçoit les messages de l'appli ntfy et peut déclencher des scénarios à partir de mots-clés ([présentation sur le forum Jeedom](https://community.jeedom.com/t/plugin-ntfy-bridge-informations/149651)).

### Sans plugin (script ou commande HTTP)

Avec le plugin Script, ou toute commande capable de lancer un shell :

```bash
curl -s -H "Title: Fuite confirmée" -H "Priority: urgent" -H "Tags: rotating_light" \
     -d "Consommation continue depuis 24 h." https://ntfy.sh/eau-3f9c2a7d1b6e4f0a8c5d2e71
```

---

## Domoticz

Configuration → Paramètres → **Notifications** → **HTTP personnalisé/Action** ([wiki Domoticz](https://wiki.domoticz.com/Notifications)) :

| Champ | Valeur |
|---|---|
| Activer | coché |
| #TO | `eau-3f9c2a7d1b6e4f0a8c5d2e71` (le sujet) |
| URL/Action | `https://ntfy.sh/` |
| POST Data | `{"topic":"#TO","title":"#SUBJECT","message":"#MESSAGE","tags":["droplet"]}` |
| POST Content-Type | `application/json` |
| POST Headers | vide, ou `Authorization: Bearer tk_…` si serveur protégé |

Toutes les notifications Domoticz (seuils, interrupteurs, scripts dzVents avec `domoticz.notify(...)`) passent alors par ntfy. Les priorités de Domoticz (−2 à 2) ne correspondent pas à celles de ntfy (1 à 5) : pour un message urgent, crée une seconde entrée ou un script dzVents qui appelle `domoticz.openURL` avec `"priority": 5`.

---

## openHAB

Dans une règle (Rules DSL) :

```java
val headers = newHashMap("Content-Type" -> "application/json")
// headers.put("Authorization", "Bearer tk_…")   // serveur protégé
val json = '{"topic":"eau-3f9c2a7d1b6e4f0a8c5d2e71","title":"Débit anormal","message":"' +
           DebitEstime.state.toString + ' L/h","priority":5,"tags":["warning","droplet"]}'
sendHttpPostRequest("https://ntfy.sh/", "application/json", json, headers, 5000)
```

---

## Node-RED

Nœud **function**, puis nœud **http request** (méthode `POST`, URL `https://ntfy.sh/`, retour « a parsed JSON object ») :

```javascript
msg.headers = { "Content-Type": "application/json" };   // + Authorization si besoin
msg.payload = {
  topic: "eau-3f9c2a7d1b6e4f0a8c5d2e71",
  title: "Eau : bilan du jour",
  message: `Conso aujourd'hui : ${msg.payload} L`,
  priority: 2,
  tags: ["droplet"]
};
return msg;
```

---

## Script, cron, NAS, routeur…

```bash
# forme simple
curl -s -d "Conso aujourd'hui : 123 L" -H "Title: Eau" -H "Tags: droplet" https://ntfy.sh/eau-3f9c2a7d1b6e4f0a8c5d2e71

# forme JSON
curl -s https://ntfy.sh/ -H "Content-Type: application/json" \
     -d '{"topic":"eau-3f9c2a7d1b6e4f0a8c5d2e71","title":"Eau","message":"123 L","priority":2,"tags":["droplet"]}'

# serveur protégé
curl -s -H "Authorization: Bearer tk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx" -d "Test" https://ntfy.exemple.fr/eau-…
```

## Bonnes pratiques entre voisins

- **Un sujet par destinataire**, et chacun ne connaît que le sien.
- **Qui émet ?** Choisis une seule source par message : l'ESP pour les bilans des voisins, la domotique pour ce que l'ESP ne sait pas faire. Sinon, chacun reçoit tout en double.
- **Serveur partagé** : si plusieurs maisons publient, un [serveur ntfy privé](serveur-ntfy-docker.md) avec un compte par maison est plus sûr que des sujets publics sur ntfy.sh.
