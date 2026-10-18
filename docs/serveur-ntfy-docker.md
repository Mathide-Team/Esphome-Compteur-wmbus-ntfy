# Héberger son propre serveur ntfy (Docker et Docker Swarm)

`ntfy.sh` est gratuit et suffit pour démarrer, mais **tous ses sujets sont publics** : n'importe qui connaissant un nom de sujet peut lire les messages. Un serveur privé permet :
- des **comptes et des droits** : l'ESP peut publier sans lire, chaque voisin ne lit que son sujet ;
- de ne plus dépendre des limites de ntfy.sh (250 messages par jour et par adresse IP) ;
- de garder les données (conso des voisins) chez soi.

Sources : [installation](https://docs.ntfy.sh/install/) et [configuration](https://docs.ntfy.sh/config/) de ntfy.

## Ce qu'il faut savoir avant

- Image officielle : **`binwiederhier/ntfy`** (amd64, armv6, armv7, arm64 : un Raspberry Pi convient). Fige une version (`binwiederhier/ntfy:v2.x.y`) plutôt que `latest` en production.
- Le serveur écoute sur le **port 80** du conteneur (interface web + API). Il ne fait pas lui-même le HTTPS : place-le derrière un **reverse proxy** (Traefik, Caddy, nginx, Nginx Proxy Manager…) avec un certificat.
- L'ESP vérifie le certificat (`verify_ssl: true`). Il faut donc un **certificat valide** (Let's Encrypt). Pour un certificat auto-signé, voir `ca_certificate_path` dans le [composant http_request](https://esphome.io/components/http_request/).
- Le **WebSocket** doit passer à travers le proxy. Avec nginx : `proxy_set_header Upgrade $http_upgrade;` et `proxy_set_header Connection "upgrade";`. Traefik et Caddy le gèrent seuls.
- **iOS** : pour des notifications instantanées depuis un serveur privé, garde `upstream-base-url: https://ntfy.sh`. Seul l'identifiant du message transite par ntfy.sh, pas son contenu. Sans ce réglage, les notifications iOS peuvent arriver avec plusieurs minutes, voire plusieurs heures, de retard.
- Chaque option de configuration existe sous trois formes : clé de `server.yml` (`auth-file`), option de ligne de commande (`--auth-file`) et variable d'environnement (`NTFY_AUTH_FILE`).

## Docker Compose (un seul hôte)

Fichiers : [`docker/compose.yaml`](../docker/compose.yaml) et [`docker/.env.example`](../docker/.env.example).

```bash
cd docker
cp .env.example .env          # puis renseigne NTFY_BASE_URL=https://ntfy.exemple.fr
docker compose up -d
docker compose ps             # l'état doit passer à « healthy »
```

Réglages principaux du fichier :

| Variable | Valeur | Pourquoi |
|---|---|---|
| `NTFY_BASE_URL` | `https://ntfy.exemple.fr` | Adresse publique, utilisée dans les liens et par les applis |
| `NTFY_CACHE_FILE` | `/var/lib/ntfy/cache.db` | Messages conservés après un redémarrage (`since=…` fonctionne) |
| `NTFY_AUTH_FILE` | `/var/lib/ntfy/user.db` | Active les comptes |
| `NTFY_AUTH_DEFAULT_ACCESS` | `deny-all` | Instance privée : rien sans compte |
| `NTFY_BEHIND_PROXY` | `true` | Sans ce réglage, tous les visiteurs passant par le proxy sont comptés comme un seul pour les limites |
| `NTFY_UPSTREAM_BASE_URL` | `https://ntfy.sh` | Notifications instantanées sur iOS |
| ports | `127.0.0.1:8080:80` | N'écoute qu'en local : seul le reverse proxy y accède |

### Créer les comptes, les droits et le jeton de l'ESP

```bash
# administrateur (accès à tout)
docker exec -it ntfy ntfy user add --role=admin admin

# l'ESP : publie sur tous les sujets eau-*, sans pouvoir les lire
docker exec -it ntfy ntfy user add compteur-esp
docker exec ntfy ntfy access compteur-esp 'eau-*' write-only
docker exec ntfy ntfy token add compteur-esp          # → tk_… à mettre dans secrets.yaml (ntfy_token)

# chaque voisin : lit uniquement SON sujet
docker exec -it ntfy ntfy user add voisin1
docker exec ntfy ntfy access voisin1 eau-a81d6c0f4e2b9a7c3d5f1e08 read-only

docker exec ntfy ntfy access                          # vérifier la liste des droits
```

Côté ESP (voir le [README](../README.md#sécurité)) : `ntfy_server: "https://ntfy.exemple.fr"` et `ntfy_token: "tk_…"` dans `secrets.yaml`. L'en-tête `Authorization` est ajouté automatiquement. Côté voisin : dans l'appli ntfy, ajoute le serveur `https://ntfy.exemple.fr` avec ses identifiants `voisin1`, puis abonne-toi à son sujet.

### Sauvegarde et mise à jour

```bash
docker run --rm -v ntfy_ntfy-data:/d -v "$PWD":/b alpine tar czf /b/ntfy-$(date +%F).tgz -C /d .   # sauvegarde
docker compose pull && docker compose up -d                                                        # mise à jour
```

Le nom réel du volume (`ntfy_ntfy-data` ici) dépend du dossier : vérifie-le avec `docker volume ls`.

## Docker Swarm (cluster)

Fichiers : [`docker/stack.yaml`](../docker/stack.yaml) et [`docker/server.yml.example`](../docker/server.yml.example).

Sous Swarm, la configuration est **déclarative** : comptes, droits et jetons sont écrits dans `server.yml`, rangé dans un **secret Swarm** (chiffré dans le cluster, monté dans `/run/secrets/`). Pas besoin de `docker exec` sur un nœud précis.

### 1. Préparer `server.yml`

```bash
cd docker
cp server.yml.example server.yml
docker run --rm -it binwiederhier/ntfy user hash       # empreinte bcrypt d'un mot de passe (une par compte)
docker run --rm binwiederhier/ntfy token generate      # jeton tk_… pour l'ESP
```

Remplace les empreintes et le jeton dans `server.yml` :
- `auth-users` : `<nom>:<empreinte>:<admin|user>` ;
- `auth-access` : `<nom>:<sujet ou motif>:<rw|ro|wo|deny>` ;
- `auth-tokens` : `<nom>:<tk_…>[:<libellé>]`. Le jeton commence par `tk_` et fait 32 caractères au total.

Au démarrage, ntfy crée ou met à jour ces comptes, droits et jetons. Une entrée retirée du fichier est supprimée de la base.

### 2. Créer le secret, étiqueter le nœud, déployer

```bash
docker secret create ntfy_server_yml server.yml && shred -u server.yml   # le fichier en clair n'est plus utile
docker node update --label-add ntfy=true <nœud>                          # nœud qui garde les données
docker network create -d overlay --attachable proxy                      # si le réseau du proxy n'existe pas
docker stack deploy -c stack.yaml ntfy
docker service ps ntfy_ntfy
```

### Pourquoi ces réglages

| Réglage | Raison |
|---|---|
| `replicas: 1` | ntfy stocke tout dans des bases **SQLite** (`cache.db`, `user.db`) : deux instances sur les mêmes fichiers les corrompraient |
| `placement: node.labels.ntfy == true` | Le volume est **local à un nœud** : le service doit toujours y revenir. Pour un basculement automatique, il faut un volume partagé (NFS, GlusterFS, Ceph…), ou PostgreSQL via `database-url` |
| `update_config.order: stop-first` | Pendant une mise à jour, l'ancienne tâche s'arrête avant le démarrage de la nouvelle : jamais deux écrivains |
| `command: serve --config /run/secrets/ntfy_server_yml` | La configuration est lue depuis le secret Swarm |
| `deploy.labels` Traefik | Sous Swarm, Traefik lit les étiquettes de `deploy`, pas celles du conteneur. HTTPS et WebSocket sont gérés par Traefik |

### Modifier les comptes

Un secret Swarm ne se modifie pas : crée une nouvelle version, puis remplace-la dans le service.

```bash
docker secret create ntfy_server_yml_v2 server.yml
docker service update \
  --secret-rm ntfy_server_yml \
  --secret-add source=ntfy_server_yml_v2,target=ntfy_server_yml \
  ntfy_ntfy
```

## Vérifier le serveur

```bash
curl -s https://ntfy.exemple.fr/v1/health                                    # {"healthy":true}
curl -s -H "Authorization: Bearer tk_…" -d "test" https://ntfy.exemple.fr/eau-test-123   # publication avec le jeton de l'ESP
curl -s -u voisin1:motdepasse "https://ntfy.exemple.fr/eau-a81d…/json?poll=1"            # lecture par le voisin
```

Avec `deny-all`, une publication sans jeton doit être refusée (HTTP 401 ou 403). C'est le signe que l'instance est bien privée.
