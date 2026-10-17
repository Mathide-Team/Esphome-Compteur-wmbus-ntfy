# Notifications ntfy pour le compteur d'eau wM-Bus (sans Home Assistant)

Paquet ESPHome qui ajoute des **notifications push [ntfy](https://ntfy.sh)** au récepteur [Esphome-Compteur-wmbus](https://github.com/Mathide-Team/Esphome-Compteur-wmbus). Les messages sont envoyés **directement par l'ESP32** vers ntfy, en HTTPS. Ils ne passent **ni par Home Assistant, ni par aucune autre domotique**.

Pourquoi faire :
- **Tes alertes arrivent même si Home Assistant est arrêté** : fuite, débit anormal, conso pendant une absence, compteur muet.
- **Chaque voisin reçoit le bilan de son compteur sans avoir Home Assistant** : dans l'appli ntfy (Android, iOS, navigateur), ou dans sa propre domotique (Home Assistant, Jeedom, Domoticz, openHAB, Node-RED…), du moment qu'elle sait lire un flux HTTP.
- **Chacun ne voit que son compteur** : un sujet ntfy différent par personne.

## Ce qui est envoyé

| Destinataire | Message | Quand | Priorité ntfy |
|---|---|---|---|
| Toi | **Fuite confirmée** (avec le nombre d'heures) | Début de l'alerte | 5 (urgent) |
| Toi | **Débit anormal** (avec le débit en L/h) | Après 10 min au-dessus du seuil | 5 (urgent) |
| Toi | **Consommation pendant ton absence** | Mode absence actif et au moins 1 L sur une heure | 5 (urgent) |
| Toi | **Fuite suspectée (nuit)** | À 5 h, au moins 3 h de conso d'affilée | 4 (high) |
| Toi | **Conso journalière élevée** | Seuil journalier dépassé | 4 (high) |
| Toi | **Compteur silencieux** | Aucune trame depuis plus de 6 h | 3 (default) |
| Toi | Fin d'alerte (fuite, fuite de nuit, débit, compteur de nouveau reçu) | Retour à la normale | 2 (low) |
| Toi + chaque voisin | **Bilan du jour** : conso du jour (L) et index (m³) de **son** compteur | Chaque jour à `ntfy_heure_bilan` h (21 h par défaut) | 2 (low) |

Les seuils sont ceux de la configuration principale, réglables depuis HA ou depuis la page web de l'ESP. Les voisins n'ont pas d'alertes de fuite : la configuration principale ne calcule les alertes que pour ton compteur.

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

Ajoute les sujets aux `substitutions` existantes :

```yaml
substitutions:
  # … substitutions existantes …
  ntfy_topic_moi: !secret ntfy_topic_moi
  ntfy_topic_v1: !secret ntfy_topic_v1
  ntfy_topic_v2: !secret ntfy_topic_v2
  ntfy_topic_v3: !secret ntfy_topic_v3
  ntfy_topic_v4: !secret ntfy_topic_v4
  # facultatif :
  # ntfy_server: "https://ntfy.exemple.fr"   # ton propre serveur (défaut : https://ntfy.sh)
  # ntfy_heure_bilan: "20"                   # heure du bilan (défaut : 21)
```

Puis ajoute le paquet, au même niveau que `esphome:`. Deux possibilités :

```yaml
# a) directement depuis GitHub (mis à jour avec ce dépôt) :
packages:
  ntfy: github://Mathide-Team/Esphome-Compteur-wmbus-ntfy/ntfy.yaml@main

# b) ou fichier copié à côté de compteur-eau-lora.yaml :
packages:
  ntfy: !include ntfy.yaml
```

La configuration principale n'a pas besoin d'être modifiée ailleurs. Le paquet lit ses alertes (`bs_fuite_confirmee`…) et ses variables (`g_total`, `v1_total`…) sans y toucher.

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

## Serveur ntfy privé ou sujets protégés

- **Ton propre serveur** : `ntfy_server: "https://ntfy.exemple.fr"` dans les substitutions.
- **Sujets protégés par un jeton d'accès** : ajoute `ntfy_token: !secret ntfy_token` aux substitutions et décommente la ligne `Authorization: "Bearer ${ntfy_token}"` dans `ntfy.yaml` (copie locale, option b). ntfy accepte les jetons sous la forme `Authorization: Bearer tk_…`. Sur un serveur avec contrôle d'accès, chaque voisin peut avoir un compte qui ne lit que son sujet.

## Limites

- **Limites de ntfy.sh** : par visiteur (ici l'adresse IP de ta box), 60 requêtes d'un coup, puis 1 requête toutes les 5 s, et **250 messages par jour** au maximum. Le paquet envoie au plus 5 bilans par jour plus les alertes : on reste très loin de la limite.
- **Une seule adresse IP** : tous les messages partent de ta box. Les voisins partagent donc ta limite ntfy.sh, ce qui ne pose pas de problème vu le faible volume.
- **Redémarrage** : une alerte encore active au redémarrage de l'ESP (par exemple une fuite confirmée, mémorisée en flash) est renvoyée une fois.
- **Sans Internet**, rien n'est envoyé. Les messages ne sont pas gardés en attente : chaque envoi est tenté une seule fois.
- **Certificat** : le certificat de ntfy.sh est vérifié (`verify_ssl: true`, avec le paquet de certificats racine d'ESP-IDF). Pour un serveur auto-signé, voir l'option `ca_certificate_path` du composant [`http_request`](https://esphome.io/components/http_request/).
- **Heure** : le bilan suit l'heure Internet (SNTP, fuseau `Europe/Paris`), indépendante de Home Assistant.
- **Moins de 4 voisins** : laisse leur sujet à `""`. Si tu as supprimé un voisin de la configuration principale, supprime aussi sa ligne dans le script `ntfy_bilans`.

## Vie privée

- Le bilan d'un voisin ne part **que sur son sujet**. Ne donne à chacun que **son** sujet.
- Sur ntfy.sh, un sujet deviné = des messages lus par un inconnu : garde des noms aléatoires, ou utilise un serveur privé avec contrôle d'accès.
- Ne lis et ne partage que les compteurs dont le propriétaire est d'accord.

## Fichiers

| Fichier | Rôle |
|---|---|
| `ntfy.yaml` | Le paquet ESPHome (client HTTPS, heure SNTP, scripts d'envoi, boutons, alertes) |
| `secrets.ntfy.example.yaml` | Lignes à ajouter à ton `secrets.yaml` |
| [`docs/emetteurs.md`](docs/emetteurs.md) | Publier vers ntfy depuis Home Assistant, Jeedom, Domoticz, openHAB, Node-RED, un script |
| [`docs/serveur-ntfy-docker.md`](docs/serveur-ntfy-docker.md) | Héberger son serveur ntfy : Docker Compose et Docker Swarm |
| `exemples/home-assistant.yaml` | Automatisations HA : bilan d'un voisin et alerte de fuite via l'intégration ntfy |
| `docker/` | `compose.yaml`, `stack.yaml` (Swarm), `server.yml.example`, `.env.example` |
| `scripts/ci_assembler.py` | CI : assemble la configuration du compteur et le paquet pour `esphome config` |

Validé avec `esphome config` et compilé (`esphome compile`, ESPHome 2026.9.1) en combinaison avec `compteur-eau-lora.yaml`. Non testé sur le module réel.

## Contribuer

Le dépôt suit le socle qualité de Mathide-Team :

- **`main`** = branche de livraison, **`dev`** = branche d'intégration. On ne pousse jamais directement sur l'une ou l'autre.
- Une branche par sujet, créée depuis `dev` (`feat/<n°>-…`, `fix/<n°>-…`, `docs/…`, `ci/…`), puis une **PR vers `dev`**.
- Livraison : **PR `dev` → `main`**. Le check « Garde : PR vers main doit venir de dev » refuse toute autre branche source.
- La CI (« Qualité (lint, validation ESPHome) ») doit passer : `yamllint --strict` et `esphome config` du paquet assemblé avec la configuration principale (branche `main` d'Esphome-Compteur-wmbus). Une compilation complète tourne sur `main` et à la demande.
- Les protections de `main` et `dev` sont versionnées dans `.github/branch-protection/`. Le workflow « Protection des branches » signale chaque jour tout écart.

## Licence

[MIT](LICENSE) © 2026 Mathilde Deuscher.


