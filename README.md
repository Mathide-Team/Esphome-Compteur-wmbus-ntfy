# Notifications ntfy pour le compteur d'eau wM-Bus (sans Home Assistant)

Paquet ESPHome qui ajoute des **notifications push [ntfy](https://ntfy.sh)** au récepteur [Esphome-Compteur-wmbus](https://github.com/Mathilde-Team/Esphome-Compteur-wmbus). Les messages sont envoyés **directement par l'ESP32** vers ntfy, en HTTPS. Ils ne passent **ni par Home Assistant, ni par aucune autre domotique**.

Pourquoi faire :
- **Tes alertes arrivent même si Home Assistant est arrêté** : fuite, débit anormal, conso pendant une absence, compteur muet.
- **Chaque voisin reçoit le bilan et les alertes de son compteur sans avoir Home Assistant** : dans l'appli ntfy (Android, iOS, navigateur), ou dans sa propre domotique (Home Assistant, Jeedom, Domoticz, openHAB, Node-RED…), du moment qu'elle sait lire un flux HTTP.
- **Chacun ne voit que son compteur** : un sujet ntfy différent par personne.

## Ce qui est envoyé

| Destinataire | Message | Quand | Priorité ntfy |
|---|---|---|---|
| Toi | **Fuite confirmée** (avec le nombre d'heures) | Début de l'alerte | 5 (urgent) |
| Toi | **Débit anormal** (avec le débit en L/h) | Après 10 min au-dessus du seuil | 5 (urgent) |
| Toi | **Consommation pendant ton absence** | Mode absence actif et au moins 1 L sur une heure | 5 (urgent) |
| Toi | **Fuite suspectée (nuit)** | À 5 h, au moins 3 h de conso d'affilée | 4 (high) |
| Toi | **Conso journalière élevée** | Seuil journalier dépassé | 4 (high) |
| Toi | **Compteur silencieux** | Aucune trame depuis plus de `Compteur silencieux après` heures (6 par défaut) | 3 (default) |
| Toi | Fin d'alerte (fuite, fuite de nuit, débit, compteur de nouveau reçu) | Retour à la normale | 2 (low) |
| Chaque voisin | **Fuite confirmée**, **débit anormal** | Mêmes règles que pour toi, sur **son** compteur | 5 (urgent) |
| Chaque voisin | **Fuite suspectée (nuit)**, **conso journalière élevée** | Idem | 4 (high) |
| Chaque voisin **+ toi** | **Compteur silencieux** (toi : « Compteur de Dupont silencieux ») | Aucune trame de son compteur depuis le délai réglé | 3 (default) |
| Chaque voisin (+ toi pour le compteur silencieux) | Fin d'alerte | Retour à la normale | 2 (low) |
| Toi + chaque voisin | **Bilan du jour** : conso du jour (L) et index (m³) de **son** compteur | Chaque jour à `ntfy_heure_bilan` h (21 h par défaut) | 2 (low) |

Les seuils sont ceux de la configuration principale (les mêmes pour ton compteur et pour les voisins), réglables depuis HA ou depuis la page web de l'ESP. Chacun ne reçoit que les alertes de **son** compteur. Seule exception : un compteur voisin silencieux te prévient aussi, car c'est toi qui t'occupes du récepteur. Pas de mode absence pour les voisins.

Le paquet ajoute aussi :

| Entité | Rôle |
|---|---|
| `ntfy - notifications actives` (interrupteur) | Coupe tous les envois ntfy |
| `ntfy - message de test` (bouton) | Envoie un message de test sur ton sujet |
| `ntfy - envoyer les bilans maintenant` (bouton) | Envoie tout de suite le bilan du jour à tout le monde |

## Installation

### 1. Choisir les sujets

Sur le serveur public `ntfy.sh`, il n'y a pas de compte à créer : **le nom du sujet sert de mot de passe**. Tous les sujets y sont publics, et n'importe qui connaissant le nom peut lire les messages ([documentation ntfy](https://docs.ntfy.sh/publish/)). Choisis donc des noms longs et aléatoires (lettres, chiffres, `-` et `_`, 64 caractères maximum) :

```bash
echo "eau-$(openssl rand -hex 12)"     # un sujet par personne
```

### 2. Ajouter les sujets à `secrets.yaml`

Copie le contenu de [`secrets.ntfy.example.yaml`](secrets.ntfy.example.yaml) à la fin de ton `secrets.yaml` et remplace les sujets. `""` = pas de notification pour ce compteur.

### 3. Brancher le paquet dans `compteur-eau-lora.yaml`

Il faut la configuration principale qui déduit les voisins de `secrets.yaml` (`voisins/voisins.yaml`, et `<<: !include secrets.yaml` dans ses `substitutions`). Il suffit alors d'**une seule ligne** dans `packages:` :

```yaml
packages:
  voisins: !include voisins/voisins.yaml
  ntfy: github://Mathilde-Team/Esphome-Compteur-wmbus-ntfy/ntfy.yaml@main
  # ou, fichiers copiés à côté de compteur-eau-lora.yaml :  ntfy: !include ntfy.yaml
```

Tout le reste se règle dans `secrets.yaml` (voir `secrets.ntfy.example.yaml`) :

| Entrée de `secrets.yaml` | Rôle |
|---|---|
| `ntfy_topic_moi` | Ton sujet : alertes de ton compteur et ton bilan |
| `ntfy_topic_vN` | Sujet du voisin N (le N de `compteurN`) : son bilan et les alertes de son compteur. Absent ou `""` = rien n'est envoyé pour lui |
| `ntfy_token` | Facultatif : jeton d'accès (voir « Sécurité ») |
| `ntfy_server`, `ntfy_heure_bilan` | Facultatifs : serveur (défaut `https://ntfy.sh`) et heure du bilan (défaut 21) |

Un voisin reçoit des notifications dès que **`compteurN` et `ntfy_topic_vN`** sont présents. Le paquet inclut lui-même `ntfy-voisin.yaml` pour chacun : rien d'autre à écrire.

> **Mise à jour depuis une version précédente** :
> - retire de `compteur-eau-lora.yaml` les substitutions `ntfy_topic_moi`, `ntfy_topic_v1`…, `ntfy_token` ;
> - retire les lignes `ntfy_voisinN` de `packages:` ;
> - garde les entrées de `secrets.yaml`, inchangées.
>
> Cette version doit être déployée **en même temps** que la configuration principale qui déduit les voisins de `secrets.yaml`.

### 4. Flasher et tester

1. Flashe le module (par le WiFi : ESPHome Builder → Install → Wirelessly).
2. Abonne-toi à ton sujet dans l'appli ntfy (voir plus bas).
3. Appuie sur le bouton **`ntfy - message de test`** (page de l'appareil dans HA, ou page web de l'ESP).
4. Dans les logs, `[ntfy] Envoyé : …` = envoi réussi, `Refusé par le serveur (HTTP …)` = sujet ou jeton refusé, `Échec de l'envoi` = pas d'accès à Internet.

## Recevoir les notifications

### Avec l'appli ntfy (sans domotique)

Installe ntfy (Android : Google Play ou F-Droid ; iOS : App Store ; ou [ntfy.sh/app](https://ntfy.sh/app) dans un navigateur), touche **+**, puis saisis le nom du sujet. Pour un serveur autre que ntfy.sh, renseigne aussi son adresse.

### Avec une autre domotique

N'importe quel système capable de lire un flux HTTP peut s'abonner ([API d'abonnement ntfy](https://docs.ntfy.sh/subscribe/api/)) :

| Adresse | Contenu |
|---|---|
| `https://ntfy.sh/<sujet>/json` | Flux continu, un objet JSON par ligne |
| `https://ntfy.sh/<sujet>/sse` | Server-Sent Events |
| `https://ntfy.sh/<sujet>/ws` | WebSocket |
| `https://ntfy.sh/<sujet>/json?poll=1&since=10m` | Interrogation ponctuelle (messages des 10 dernières minutes) |
| `https://ntfy.sh/<sujet>/json?poll=1&since=latest` | Dernier message seulement |

Exemple en ligne de commande (pour un script, un Raspberry Pi, une tâche cron…) :

```bash
curl -s "https://ntfy.sh/<sujet>/json?poll=1&since=latest"
```

Chaque message JSON contient notamment `title`, `message`, `priority` et `tags`. Le filtre `?p=high,urgent` ne renvoie que les alertes, sans les bilans.

## Publier depuis une domotique

L'ESP n'est pas le seul à pouvoir émettre. Home Assistant (intégration ntfy officielle ou `rest_command`), Jeedom (plugin Ntfy), Domoticz (notification « HTTP personnalisé »), openHAB, Node-RED ou un simple script `curl` peuvent publier sur les mêmes sujets. Exemples détaillés : **[docs/emetteurs.md](docs/emetteurs.md)**.

## Héberger son serveur ntfy

Pour des sujets vraiment privés (comptes, droits par sujet, jeton pour l'ESP) : serveur ntfy avec **Docker Compose** ou **Docker Swarm**, prêt à l'emploi dans `docker/`. Guide : **[docs/serveur-ntfy-docker.md](docs/serveur-ntfy-docker.md)**.

## Format des messages

L'ESP publie en JSON sur la racine du serveur (`POST https://ntfy.sh/`), la méthode recommandée par ntfy pour les caractères accentués :

```json
{
  "topic": "eau-3f9c2a7d1b6e4f0a8c5d2e71",
  "title": "FUITE CONFIRMÉE",
  "message": "Consommation continue depuis 24 h.",
  "priority": 5,
  "tags": ["rotating_light", "droplet"]
}
```

Les `tags` sont des noms d'émojis : ntfy les affiche devant le titre.

## Sécurité

### Ce qui protège réellement un sujet

Sur ntfy.sh sans compte, **le nom du sujet est le seul secret** : quiconque le connaît peut lire les messages et en publier. Il n'existe pas de mot de passe propre à un sujet. Trois niveaux de protection :

| Mécanisme | Ce qu'il apporte | Limite |
|---|---|---|
| **Sujet aléatoire** sur ntfy.sh (`eau-` + 24 caractères hexadécimaux, voir `secrets.ntfy.example.yaml`) | Impossible à deviner | Le nom circule dans les URL, les applis et les captures d'écran. S'il fuit, n'importe qui peut lire et publier |
| **Sujets réservés** sur ntfy.sh ([offres payantes](https://ntfy.sh/)) | Le propriétaire fixe les droits des autres : `deny-all` (lui seul), lecture seule pour tous, etc. ([notes de version ntfy](https://docs.ntfy.sh/releases/)) | En `deny-all`, chaque lecteur doit avoir un compte ou ton jeton. En « lecture pour tous », seule l'écriture est protégée, contre les fausses alertes |
| **Serveur privé** avec contrôle d'accès ([`docs/serveur-ntfy-docker.md`](docs/serveur-ntfy-docker.md)) | Droits par compte et par sujet : lecture seule, écriture seule ou refus ([configuration ntfy](https://docs.ntfy.sh/config/)) | Il faut l'héberger (fichiers Docker et Swarm fournis) |

### Le jeton de l'ESP

1. Mets le jeton dans `secrets.yaml` : `ntfy_token: "tk_…"`.
2. L'en-tête `Authorization: Bearer tk_…` n'est envoyé **que si le jeton est renseigné**. Sans jeton (`""`, valeur par défaut), le paquet fonctionne comme avant sur ntfy.sh : un en-tête vide vaut « anonyme ».

Recommandations :
- **Un jeton vaut le compte entier.** Avec un jeton, on peut tout faire sauf changer le mot de passe et supprimer le compte. Les jetons limités ne sont pas encore disponibles ([configuration ntfy](https://docs.ntfy.sh/config/)). Les droits se règlent donc **sur le compte**, pas sur le jeton.
- **L'ESP a son propre compte, en écriture seule** : `compteur-esp:eau-*:wo` (déjà dans [`docker/server.yml.example`](docker/server.yml.example)). Si le module est volé et sa mémoire lue, le voleur peut seulement publier de fausses alertes : il ne lit rien et n'accède à aucun autre sujet. Il suffit alors de révoquer ce jeton.
- **Chaque voisin a un compte en lecture seule sur son seul sujet** (`voisin1:eau-…:ro`). C'est le seul réglage où chacun ne voit vraiment que son compteur.
- **Jamais de `?auth=` dans l'URL.** ntfy l'accepte ([publication ntfy](https://docs.ntfy.sh/publish/)), mais une URL finit dans les journaux et les historiques. Le paquet utilise l'en-tête, en HTTPS avec certificat vérifié (`verify_ssl: true`).
- Le jeton est **compilé dans le firmware** et apparaît en clair dans la sortie de `esphome config`. Ne partage ni le `.bin`, ni ton `secrets.yaml`, ni cette sortie.

### Changer de jeton (rotation)

1. Crée un nouveau jeton pour le compte de l'ESP : `ntfy token add compteur-esp` (ou `docker exec ntfy ntfy token add compteur-esp`).
2. Mets-le dans `secrets.yaml`, puis installe le firmware par le WiFi (**Install → Wirelessly**).
3. Vérifie l'envoi avec **« ntfy - message de test »**, puis révoque l'ancien jeton : `ntfy token remove compteur-esp tk_…`.

Dans les journaux de l'ESP, `Refusé (HTTP 401/403)` veut dire jeton absent, révoqué, ou sans droit d'écriture sur ce sujet.

### Si un sujet a fuité

1. Génère un nouveau sujet : `echo "eau-$(openssl rand -hex 12)"`.
2. Remplace-le dans `secrets.yaml` (et dans les droits du serveur privé : `auth-access`), puis réinstalle par le WiFi.
3. Préviens la personne concernée, qui s'abonne au nouveau sujet et supprime l'ancien dans son appli.
4. Sur un serveur privé, si le jeton de l'ESP a pu fuiter aussi : fais une rotation (ci-dessus).

### Limites à connaître

- **Pas de chiffrement de bout en bout.** Le serveur voit le texte des messages. Le chiffrement est encore une demande ouverte côté ntfy ([ticket #69](https://github.com/binwiederhier/ntfy/issues/69)). Les messages sont gardés **12 h** en cache par défaut ([publication ntfy](https://docs.ntfy.sh/publish/)).
- **Le contrôle d'accès et le chiffrement sont deux protections différentes.** Un serveur privé `deny-all` empêche les inconnus de lire, mais l'administrateur du serveur lit tout.
- **Moins de données, moins de risque** : les messages ne contiennent que la conso et l'index, jamais le numéro du compteur. Le titre du bilan d'un voisin contient son nom (`nomcompteurN`) et part sur **son** sujet. Si ce sujet peut être lu par d'autres, mets un prénom ou un surnom dans `nomcompteurN`.

### Ma recommandation

- **Toi seul, ou des voisins de confiance** : ntfy.sh avec des sujets aléatoires suffit. Prévois de changer de sujet si l'un d'eux circule.
- **Plusieurs voisins, ou des données que tu veux garder privées** : un serveur ntfy privé en `deny-all`, avec un compte ESP en écriture seule et un compte en lecture seule par voisin.
- **Payer ntfy.sh** sert surtout contre les fausses alertes (sujets réservés en « lecture pour tous, écriture pour moi »), ou pour une lecture privée avec des comptes en `deny-all`.

### Ton propre serveur

`ntfy_server: "https://ntfy.exemple.fr"` dans `secrets.yaml`. Voir [`docs/serveur-ntfy-docker.md`](docs/serveur-ntfy-docker.md).

## Limites

- **Limites de ntfy.sh** : par visiteur (ici l'adresse IP de ta box), 60 requêtes d'un coup, puis 1 requête toutes les 5 s, et **250 messages par jour** au maximum. Le paquet envoie au plus 11 bilans par jour (toi + 10 voisins) plus les alertes : on reste très loin de la limite.
- **Une seule adresse IP** : tous les messages partent de ta box. Les voisins partagent donc ta limite ntfy.sh, ce qui ne pose pas de problème vu le faible volume.
- **Redémarrage** : une alerte encore active au redémarrage de l'ESP (par exemple une fuite confirmée, mémorisée en flash) est renvoyée une fois.
- **Sans Internet**, rien n'est envoyé. Les messages ne sont pas gardés en attente : chaque envoi est tenté une seule fois.
- **Certificat** : le certificat de ntfy.sh est vérifié (`verify_ssl: true`, avec le paquet de certificats racine d'ESP-IDF). Pour un serveur auto-signé, voir l'option `ca_certificate_path` du composant [`http_request`](https://esphome.io/components/http_request/).
- **Heure** : le bilan suit l'heure Internet (SNTP, fuseau `Europe/Paris`), indépendante de Home Assistant.
- **Nombre de voisins** : de 0 à 10, déduits de `secrets.yaml`. Sans `ntfy_topic_vN` (ou avec `""`), rien n'est envoyé pour ce voisin. Avec 10 voisins, une même alerte touche au plus 11 sujets, et la file d'envoi (`max_runs: 32`) les traite l'un après l'autre.

## Vie privée

- Le bilan d'un voisin ne part **que sur son sujet**. Ne donne à chacun que **son** sujet.
- Sur ntfy.sh, un sujet deviné = des messages lus par un inconnu : garde des noms aléatoires, ou utilise un serveur privé avec contrôle d'accès.
- Ne lis et ne partage que les compteurs dont le propriétaire est d'accord.

## Fichiers

| Fichier | Rôle |
|---|---|
| `ntfy.yaml` | Le paquet ESPHome (client HTTPS, heure SNTP, scripts d'envoi, boutons, alertes de ton compteur) |
| `ntfy-voisin.yaml` | Modèle d'un voisin : son bilan et les alertes de son compteur, sur son sujet (inclus par `ntfy.yaml` pour chaque voisin qui a un sujet) |
| `secrets.ntfy.example.yaml` | Lignes à ajouter à ton `secrets.yaml` |
| [`docs/emetteurs.md`](docs/emetteurs.md) | Publier vers ntfy depuis Home Assistant, Jeedom, Domoticz, openHAB, Node-RED, un script |
| [`docs/serveur-ntfy-docker.md`](docs/serveur-ntfy-docker.md) | Héberger son serveur ntfy : Docker Compose et Docker Swarm |
| `exemples/home-assistant.yaml` | Automatisations HA : bilan d'un voisin et alerte de fuite via l'intégration ntfy |
| `docker/` | `compose.yaml`, `stack.yaml` (Swarm), `server.yml.example`, `.env.example` |
| `scripts/ci_assembler.py` | CI : assemble la configuration du compteur et le paquet pour `esphome config` |

Validé avec `esphome config` et compilé (`esphome compile`, ESPHome 2026.9.1) en combinaison avec `compteur-eau-lora.yaml`. Non testé sur le module réel.

## Contribuer

Le dépôt suit le socle qualité de Mathilde-Team :

- **`main`** = branche de livraison, **`dev`** = branche d'intégration. On ne pousse jamais directement sur l'une ou l'autre.
- Une branche par sujet, créée depuis `dev` (`feat/<n°>-…`, `fix/<n°>-…`, `docs/…`, `ci/…`), puis une **PR vers `dev`**.
- Livraison : **PR `dev` → `main`**. Le check « Garde : PR vers main doit venir de dev » refuse toute autre branche source.
- La CI (« Qualité (lint, validation ESPHome) ») doit passer : `yamllint --strict` et `esphome config` du paquet assemblé avec la configuration principale (branche `main` d'Esphome-Compteur-wmbus). Une compilation complète tourne sur `main` et à la demande.
- Les protections de `main` et `dev` sont versionnées dans `.github/branch-protection/`. Le workflow « Protection des branches » signale chaque jour tout écart.

## Licence

[MIT](LICENSE) © 2026 Mathilde Deuscher.


