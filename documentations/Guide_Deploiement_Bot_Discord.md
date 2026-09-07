# Déploiement d’un bot Discord Python sur serveur Ubuntu

**Docker, secrets, SQLite, migration ciblée et validation — procédure anonymisée**

> Ce document reconstruit uniquement le chemin **validé et fonctionnel** du déploiement. Les essais infructueux, commandes corrigées en cours de route et données d’identification ont volontairement été omis.

## 1. Objectif et périmètre

Le but est de déployer un bot Discord Python sur un serveur Ubuntu headless, dans Docker, avec :

- dépôt Git privé récupéré via une clé de déploiement dédiée en lecture seule ;
- secrets stockés hors du dépôt et hors de l’image Docker ;
- conteneur exécuté avec un utilisateur non-root ;
- base SQLite persistée sur l’hôte ;
- initialisation de la base directement sur le serveur cible ;
- synchronisation initiale depuis Discord ;
- migration **ciblée** des seules métadonnées utiles depuis l’ancienne base locale ;
- contrôles d’intégrité avant et après la migration ;
- redémarrage et validation fonctionnelle finale.

Cette procédure suppose que le serveur dispose déjà de Linux, SSH, Git, Docker Engine et Docker Compose.

## 2. Convention d’anonymisation

Les noms réels ne sont pas nécessaires pour reproduire l’architecture. Les placeholders suivants sont utilisés :

| Placeholder | Signification |
|---|---|
| `<SERVER_ID>` | nom logique du serveur utilisé dans l’arborescence |
| `<SERVER_USER>` | utilisateur Linux d’administration |
| `<SERVER_IP>` | adresse IP ou nom DNS du serveur |
| `<PROJECT>` | nom du projet / service |
| `<GITHUB_OWNER>` | propriétaire du dépôt GitHub |
| `<REPOSITORY>` | nom du dépôt privé |
| `<DEPLOY_BRANCH>` | branche de déploiement |
| `<GITHUB_ALIAS>` | alias SSH local dédié au dépôt |
| `<BOT_ENTRYPOINT>` | point d’entrée console déclaré par le projet Python |

Arborescence retenue :

```text
/srv/<SERVER_ID>/
├── apps/       # code source cloné depuis Git
├── stacks/     # fichiers Compose spécifiques au serveur
├── data/       # données persistantes des services
├── backups/    # sauvegardes avant/après opérations sensibles
└── secrets/    # fichiers de secrets, protégés par root
```

Pour le bot :

```text
/srv/<SERVER_ID>/apps/<PROJECT>
/srv/<SERVER_ID>/stacks/<PROJECT>
/srv/<SERVER_ID>/data/<PROJECT>
/srv/<SERVER_ID>/secrets/<PROJECT>.env
```

## 3. Préparation de la branche de déploiement

Une branche dédiée est créée afin de séparer les adaptations de déploiement de la branche principale :

```bash
git switch -c <DEPLOY_BRANCH>
git push -u origin <DEPLOY_BRANCH>
```

Avant publication, la suite de tests du projet est exécutée. Le déploiement ne doit partir que d’un état où tous les tests attendus passent.

### 3.1 Dockerfile de production

Le projet utilise Python 3.12 et s’exécute dans une image légère. Un utilisateur interne dédié, UID/GID `10001`, évite d’exécuter le bot en root.

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 bot \
    && useradd \
        --uid 10001 \
        --gid bot \
        --create-home \
        --shell /usr/sbin/nologin \
        bot

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

USER bot

CMD ["<BOT_ENTRYPOINT>"]
```

**Pourquoi ces choix :**

- `python:3.12-slim` réduit la surface et le poids de l’image ;
- `PYTHONDONTWRITEBYTECODE=1` évite les fichiers `.pyc` inutiles dans le conteneur ;
- `PYTHONUNBUFFERED=1` rend les logs immédiatement visibles ;
- `PIP_NO_CACHE_DIR=1` évite de conserver le cache pip dans l’image ;
- l’UID/GID fixe permet d’aligner proprement les permissions du volume SQLite sur l’hôte ;
- `USER bot` empêche l’application de tourner avec les privilèges root.

### 3.2 `.dockerignore`

Le contexte de build ne doit contenir ni secrets, ni base locale, ni artefacts de développement :

```text
.git
.gitignore

.venv
venv
__pycache__
*.pyc
*.pyo

.pytest_cache
.ruff_cache
.coverage
htmlcov

.vscode

.env
.env.*
!.env.example

data
*.db
*.db-shm
*.db-wal

tests
documentations
```

Le point crucial est que `.env` et les fichiers SQLite ne sont **jamais copiés dans l’image Docker**.

## 4. Accès au dépôt Git privé depuis le serveur

Le serveur reçoit une clé SSH dédiée à ce dépôt uniquement. Elle est ajoutée sur GitHub comme **Deploy key en lecture seule**.

### 4.1 Génération de la clé

Sur le serveur :

```bash
ssh-keygen -t ed25519 \
  -f ~/.ssh/<PROJECT>_deploy \
  -C "<SERVER_ID>-<PROJECT>-deploy"
```

Pour un déploiement automatisable, la clé n’utilise pas de passphrase. La clé publique est ensuite copiée dans :

**GitHub → Repository Settings → Deploy keys → Add deploy key**

L’option d’écriture reste désactivée.

### 4.2 Alias SSH dédié

Dans `~/.ssh/config` :

```text
Host <GITHUB_ALIAS>
    HostName github.com
    User git
    IdentityFile ~/.ssh/<PROJECT>_deploy
    IdentitiesOnly yes
```

Puis :

```bash
chmod 600 ~/.ssh/config
ssh -T <GITHUB_ALIAS>
```

Une authentification réussie confirme que la clé est valide, sans donner d’accès shell à GitHub.

### 4.3 Clone de la branche de déploiement

```bash
cd /srv/<SERVER_ID>/apps

git clone \
  --branch <DEPLOY_BRANCH> \
  --single-branch \
  git@<GITHUB_ALIAS>:<GITHUB_OWNER>/<REPOSITORY>.git \
  <PROJECT>
```

## 5. Préparation des répertoires serveur

```bash
sudo mkdir -p \
  /srv/<SERVER_ID>/data/<PROJECT> \
  /srv/<SERVER_ID>/secrets \
  /srv/<SERVER_ID>/stacks/<PROJECT>
```

Le répertoire de données appartient à l’UID/GID du conteneur :

```bash
sudo chown -R 10001:10001 /srv/<SERVER_ID>/data/<PROJECT>
sudo chmod 750 /srv/<SERVER_ID>/data/<PROJECT>
```

Le répertoire de secrets est réservé à root :

```bash
sudo chown root:root /srv/<SERVER_ID>/secrets
sudo chmod 700 /srv/<SERVER_ID>/secrets
```

Le dossier Compose reste administrable par l’utilisateur Linux :

```bash
sudo chown -R <SERVER_USER>:<SERVER_USER> \
  /srv/<SERVER_ID>/stacks/<PROJECT>
```

Cette séparation évite de mélanger **code**, **configuration de déploiement**, **secrets** et **données persistantes**.

## 6. Transfert et protection du `.env`

Le `.env` local contient notamment les secrets et identifiants Discord. Il n’est jamais envoyé vers Git.

Depuis le poste Windows, à la racine du projet :

```powershell
scp .\.env <SERVER_USER>@<SERVER_IP>:/home/<SERVER_USER>/<PROJECT>.env.tmp
```

Sur le serveur :

```bash
sudo install \
  -o root \
  -g root \
  -m 600 \
  /home/<SERVER_USER>/<PROJECT>.env.tmp \
  /srv/<SERVER_ID>/secrets/<PROJECT>.env

rm /home/<SERVER_USER>/<PROJECT>.env.tmp
```

Le fichier final est donc lisible et modifiable uniquement par root.

Exemple de variables attendues par l’application :

```text
DISCORD_TOKEN=...
DISCORD_GUILD_ID=...
DATABASE_PATH=...
ADMIN_REPORT_FORUM_ID=...
```

Les valeurs ne doivent jamais apparaître dans une documentation, un log partagé ou un dépôt Git.

## 7. Configuration Docker Compose

Le fichier serveur est créé dans :

```text
/srv/<SERVER_ID>/stacks/<PROJECT>/compose.yaml
```

Exemple validé :

```yaml
services:
  bot:
    build:
      context: /srv/<SERVER_ID>/apps/<PROJECT>
      dockerfile: Dockerfile

    container_name: <PROJECT>

    env_file:
      - /srv/<SERVER_ID>/secrets/<PROJECT>.env

    environment:
      DATABASE_PATH: /data/app.db

    volumes:
      - type: bind
        source: /srv/<SERVER_ID>/data/<PROJECT>
        target: /data

    restart: unless-stopped

    security_opt:
      - no-new-privileges:true

    cap_drop:
      - ALL

    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "5"
```

### Pourquoi surcharger `DATABASE_PATH` dans Compose ?

Le `.env` peut rester compatible avec un environnement local tandis que le déploiement impose son propre chemin persistant `/data/app.db`.

### Pourquoi aucun `ports:` ?

Un bot Discord ouvre une connexion **sortante** vers Discord. Il n’a pas besoin d’exposer un port entrant tant qu’il n’héberge pas lui-même une API ou une interface web.

### Durcissement retenu

- `restart: unless-stopped` : redémarrage automatique après reboot ou crash ;
- `no-new-privileges:true` : un processus ne peut pas gagner de nouveaux privilèges ;
- `cap_drop: ALL` : retrait des capacités Linux inutiles ;
- rotation des logs Docker : protection contre un remplissage progressif du SSD.

Avant le premier démarrage :

```bash
cd /srv/<SERVER_ID>/stacks/<PROJECT>
sudo docker compose config
```

Ne pas publier la sortie complète si elle contient des variables sensibles.

## 8. Premier build et premier démarrage

```bash
cd /srv/<SERVER_ID>/stacks/<PROJECT>

sudo docker compose build
sudo docker compose up -d
sudo docker compose ps
sudo docker compose logs --tail=100 bot
```

Les vérifications attendues sont :

- le conteneur reste `Up` ;
- aucune erreur de lecture des variables d’environnement ;
- aucune erreur de permission sur `/data` ;
- connexion Discord réussie ;
- aucune migration de schéma lancée implicitement si l’application prévoit une commande d’administration dédiée.

## 9. Initialisation propre de la base de production

La base de production n’est **pas** remplacée par la base locale historique.

La stratégie retenue est :

1. démarrer avec un répertoire de données vide ;
2. laisser le bot se connecter à Discord ;
3. initialiser la base via la commande d’administration prévue par l’application ;
4. initialiser la configuration persistante du serveur avec le bootstrap de guilde ;
5. effectuer la synchronisation des catalogues depuis Discord ;
6. ne migrer ensuite que les métadonnées humaines encore utiles.

Commandes Discord utilisées :

```text
/claviger database initialize
/claviger guild bootstrap
```

Le `guild bootstrap` est nécessaire pour créer la configuration persistante du serveur et activer les fonctionnalités prévues par la policy, notamment la gestion des rôles membre. Sans cette étape, certaines commandes peuvent rester désactivées même si la base et les catalogues sont correctement initialisés.

Après initialisation, vérifier la présence de la base :

```bash
sudo ls -lh /srv/<SERVER_ID>/data/<PROJECT>
```

Puis lancer la synchronisation des catalogues depuis Discord.

Cette approche garantit que le **schéma de production** est créé par la version réellement déployée du logiciel.

## 10. Définition du périmètre de migration SQLite

Après la synchronisation initiale, les lignes structurelles existent déjà dans la base serveur.

Les seules données historiques à conserver sont les métadonnées humaines des tables :

```text
guild_member_interests
guild_adult_accesses
```

Colonnes migrées :

```text
label
description
emoji
```

Les données suivantes restent celles recréées ou synchronisées sur le serveur :

- `guild_id` ;
- `role_id` ;
- noms de rôles et de salons ;
- clés fonctionnelles ;
- informations de présence/synchronisation Discord ;
- autres paramètres de guilde ;
- schéma et version de migration.

Le principe est donc : **la nouvelle base reste la référence structurelle ; l’ancienne base n’est qu’une source de métadonnées.**

## 11. Création d’une copie cohérente de l’ancienne base locale

Sur Windows, à la racine du projet, utiliser explicitement le Python du virtualenv :

```powershell
Remove-Item .\source.db -ErrorAction SilentlyContinue

.\.venv\Scripts\python.exe -c "import sqlite3; src=sqlite3.connect(r'data\app.db'); dst=sqlite3.connect(r'source.db'); src.backup(dst); print('Integrity:', dst.execute('PRAGMA integrity_check').fetchone()[0]); print('Schema:', dst.execute('PRAGMA user_version').fetchone()[0]); dst.close(); src.close()"
```

Résultat attendu :

```text
Integrity: ok
Schema: <CURRENT_SCHEMA_VERSION>
```

L’API `sqlite3.Connection.backup()` produit une copie cohérente, y compris lorsque la base source utilise le journal WAL.

## 12. Transfert de la base source vers le serveur

Depuis Windows :

```powershell
scp .\source.db <SERVER_USER>@<SERVER_IP>:/home/<SERVER_USER>/source.db
```

Sur le serveur, placer cette copie à côté de la production :

```bash
sudo cp /home/<SERVER_USER>/source.db \
  /srv/<SERVER_ID>/data/<PROJECT>/source.db

sudo chown 10001:10001 \
  /srv/<SERVER_ID>/data/<PROJECT>/source.db

sudo chmod 600 \
  /srv/<SERVER_ID>/data/<PROJECT>/source.db

rm /home/<SERVER_USER>/source.db
```

À ce stade :

```text
/srv/<SERVER_ID>/data/<PROJECT>/
├── app.db       # production fraîchement initialisée et synchronisée
└── source.db    # ancienne base locale, temporaire
```

## 13. Arrêt contrôlé du bot avant modification SQLite

```bash
cd /srv/<SERVER_ID>/stacks/<PROJECT>
sudo docker compose stop bot
```

Vérifier qu’aucune instance du service n’est encore active :

```bash
sudo docker compose ps
sudo docker ps --format "table {{.Names}}\t{{.Status}}" | grep -i <PROJECT>
```

Le bot peut mettre quelques secondes à apparaître hors ligne dans Discord. L’opération SQLite ne commence qu’une fois l’instance réellement arrêtée.

## 14. Sauvegarde de la production avant migration

Avec le bot arrêté :

```bash
sudo python3 - <<'PY'
import sqlite3

src = sqlite3.connect("/srv/<SERVER_ID>/data/<PROJECT>/app.db")
dst = sqlite3.connect("/srv/<SERVER_ID>/backups/<PROJECT>-before-metadata-import.db")

src.backup(dst)

print("Integrity:", dst.execute("PRAGMA integrity_check").fetchone()[0])
print("Schema:", dst.execute("PRAGMA user_version").fetchone()[0])

dst.close()
src.close()
PY
```

Attendu :

```text
Integrity: ok
Schema: <CURRENT_SCHEMA_VERSION>
```

Cette sauvegarde permet un retour arrière immédiat en cas d’erreur humaine ou de migration inattendue.

## 15. Audit des correspondances avant écriture

Avant tout `UPDATE`, comparer uniquement les **comptages**. Aucune description ni donnée utilisateur n’a besoin d’être affichée.

```bash
sudo python3 - <<'PY'
import sqlite3

prod = "/srv/<SERVER_ID>/data/<PROJECT>/app.db"
source = "/srv/<SERVER_ID>/data/<PROJECT>/source.db"

db = sqlite3.connect(prod)
db.execute("ATTACH DATABASE ? AS source", (source,))

for table in ("guild_member_interests", "guild_adult_accesses"):
    prod_total = db.execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0]

    source_total = db.execute(
        f"SELECT COUNT(*) FROM source.{table}"
    ).fetchone()[0]

    source_enriched = db.execute(
        f"""
        SELECT COUNT(*)
        FROM source.{table}
        WHERE label IS NOT NULL
           OR description IS NOT NULL
           OR emoji IS NOT NULL
        """
    ).fetchone()[0]

    matched_enriched = db.execute(
        f"""
        SELECT COUNT(*)
        FROM source.{table} AS s
        JOIN {table} AS p
          ON p.guild_id = s.guild_id
         AND p.role_id = s.role_id
        WHERE s.label IS NOT NULL
           OR s.description IS NOT NULL
           OR s.emoji IS NOT NULL
        """
    ).fetchone()[0]

    print()
    print(table)
    print("  Production rows :", prod_total)
    print("  Source rows     :", source_total)
    print("  Source enriched :", source_enriched)
    print("  Matched enriched:", matched_enriched)
    print("  Unmatched       :", source_enriched - matched_enriched)

db.close()
PY
```

Critère d’acceptation pour chaque table :

```text
Source enriched == Matched enriched
Unmatched == 0
```

Si ce critère n’est pas respecté, **ne pas lancer la migration** avant d’avoir compris les différences.

## 16. Migration transactionnelle des métadonnées

Une fois les correspondances validées :

```bash
sudo python3 - <<'PY'
import sqlite3

prod = "/srv/<SERVER_ID>/data/<PROJECT>/app.db"
source = "/srv/<SERVER_ID>/data/<PROJECT>/source.db"

tables = (
    "guild_member_interests",
    "guild_adult_accesses",
)

db = sqlite3.connect(prod)

try:
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("ATTACH DATABASE ? AS source", (source,))
    db.execute("BEGIN IMMEDIATE")

    print("=== Import des métadonnées ===")

    for table in tables:
        before = db.execute(
            f"""
            SELECT COUNT(*)
            FROM {table} p
            JOIN source.{table} s
              ON s.guild_id = p.guild_id
             AND s.role_id = p.role_id
            WHERE NOT (
                p.label IS s.label
                AND p.description IS s.description
                AND p.emoji IS s.emoji
            )
            """
        ).fetchone()[0]

        db.execute(
            f"""
            UPDATE {table}
            SET
                label = (
                    SELECT s.label
                    FROM source.{table} s
                    WHERE s.guild_id = {table}.guild_id
                      AND s.role_id = {table}.role_id
                ),
                description = (
                    SELECT s.description
                    FROM source.{table} s
                    WHERE s.guild_id = {table}.guild_id
                      AND s.role_id = {table}.role_id
                ),
                emoji = (
                    SELECT s.emoji
                    FROM source.{table} s
                    WHERE s.guild_id = {table}.guild_id
                      AND s.role_id = {table}.role_id
                )
            WHERE EXISTS (
                SELECT 1
                FROM source.{table} s
                WHERE s.guild_id = {table}.guild_id
                  AND s.role_id = {table}.role_id
            )
            """
        )

        remaining = db.execute(
            f"""
            SELECT COUNT(*)
            FROM {table} p
            JOIN source.{table} s
              ON s.guild_id = p.guild_id
             AND s.role_id = p.role_id
            WHERE NOT (
                p.label IS s.label
                AND p.description IS s.description
                AND p.emoji IS s.emoji
            )
            """
        ).fetchone()[0]

        print(f"{table}:")
        print(f"  Lignes nécessitant une mise à jour : {before}")
        print(f"  Différences restantes              : {remaining}")

        if remaining != 0:
            raise RuntimeError(
                f"{table}: des métadonnées diffèrent encore après l'import"
            )

    integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    foreign_keys = db.execute("PRAGMA foreign_key_check").fetchall()

    print()
    print("Integrity check :", integrity)
    print("Foreign keys    :", "ok" if not foreign_keys else foreign_keys)

    if integrity != "ok" or foreign_keys:
        raise RuntimeError("Échec des contrôles SQLite")

    db.commit()
    print()
    print("COMMIT effectué : migration terminée avec succès.")

except Exception as exc:
    db.rollback()
    print()
    print("ROLLBACK effectué :", exc)
    raise

finally:
    db.close()
PY
```

Critères de succès :

```text
Différences restantes : 0
Integrity check : ok
Foreign keys    : ok
COMMIT effectué : migration terminée avec succès.
```

### Pourquoi cette migration est sûre

- `BEGIN IMMEDIATE` ouvre une transaction d’écriture explicite ;
- les lignes sont reliées par `(guild_id, role_id)` ;
- seules `label`, `description` et `emoji` sont modifiées ;
- l’opérateur SQLite `IS` compare correctement les valeurs `NULL` ;
- en cas d’exception, un `ROLLBACK` annule la transaction ;
- `PRAGMA integrity_check` valide la structure SQLite ;
- `PRAGMA foreign_key_check` détecte les références incohérentes.

## 17. Sauvegarde après migration et nettoyage

Créer une nouvelle sauvegarde de l’état validé :

```bash
sudo python3 - <<'PY'
import sqlite3

src = sqlite3.connect("/srv/<SERVER_ID>/data/<PROJECT>/app.db")
dst = sqlite3.connect("/srv/<SERVER_ID>/backups/<PROJECT>-after-metadata-import.db")

src.backup(dst)

print("Integrity:", dst.execute("PRAGMA integrity_check").fetchone()[0])
print("Schema:", dst.execute("PRAGMA user_version").fetchone()[0])

dst.close()
src.close()
PY
```

Puis supprimer la base temporaire :

```bash
sudo rm /srv/<SERVER_ID>/data/<PROJECT>/source.db
```

À partir de cet instant, une seule base opérationnelle subsiste dans le répertoire de données.

## 18. Redémarrage du service

```bash
cd /srv/<SERVER_ID>/stacks/<PROJECT>

sudo docker compose up -d bot
sudo docker compose ps
sudo docker compose logs --tail=100 bot
```

Vérifier :

- conteneur `Up` ;
- connexion Discord réussie ;
- aucune erreur SQLite ;
- aucune erreur de permissions ;
- aucune exception de démarrage.

## 19. Validation fonctionnelle finale

Deux tests fonctionnels permettent de valider à la fois la migration et le comportement de synchronisation :

1. exécuter la commande de progression/configuration du catalogue ;
2. confirmer que les catalogues déjà complétés sont reconnus comme configurés ;
3. relancer un `Catalog Sync` ;
4. réexécuter la commande de progression ;
5. confirmer que le sync n’a pas écrasé `label`, `description` ou `emoji`.

Résultat attendu :

```text
Tous les catalogues disponibles sont configurés.
```

Ce résultat confirme que :

- la base de production a été créée nativement sur le serveur ;
- le catalogue Discord a été synchronisé correctement ;
- les métadonnées historiques ont été récupérées ;
- une synchronisation ultérieure préserve les champs éditoriaux ;
- le bot peut désormais fonctionner de façon permanente sur le serveur.

## 20. État final de l’architecture

```text
GitHub privé
   │
   │ Deploy key SSH read-only
   ▼
/srv/<SERVER_ID>/apps/<PROJECT>
   │
   │ Docker build
   ▼
Conteneur Python non-root (UID 10001)
   │
   ├── secrets injectés depuis
   │   /srv/<SERVER_ID>/secrets/<PROJECT>.env
   │
   └── SQLite persistante via bind mount
       /srv/<SERVER_ID>/data/<PROJECT>/app.db

Configuration Docker Compose :
/srv/<SERVER_ID>/stacks/<PROJECT>/compose.yaml

Sauvegardes :
/srv/<SERVER_ID>/backups/
```

## 21. Principes à conserver pour les futurs déploiements

### Ne pas embarquer les secrets dans Git ou dans l’image

Le dépôt contient le code et les exemples de configuration, jamais les valeurs réelles.

### Ne pas exécuter l’application en root

Les droits sont accordés uniquement aux répertoires nécessaires au service.

### Séparer le schéma des données historiques

Lors d’un changement de machine, il est souvent plus robuste de :

1. initialiser une base neuve avec la version actuelle ;
2. synchroniser les données appartenant à un système externe ;
3. importer uniquement les données métier qu’il faut réellement conserver.

### Arrêter le processus avant une modification SQLite manuelle

Cela évite les écritures concurrentes et simplifie considérablement les opérations de maintenance.

### Toujours auditer avant d’écrire

Un simple comptage `matched/unmatched` permet de détecter un changement d’identifiant ou de structure **avant** qu’une migration ne modifie la production.

### Utiliser l’API de backup SQLite

`Connection.backup()` est préférable à une copie naïve lorsqu’une base est susceptible d’utiliser WAL ou d’être ouverte par une application.

### Garder une sauvegarde avant et après toute migration manuelle

On obtient ainsi deux points de restauration clairement identifiés.

## 22. Checklist de reconstruction rapide

- [ ] Branche de déploiement propre et testée
- [ ] `Dockerfile` non-root
- [ ] `.dockerignore` excluant secrets, DB et caches
- [ ] Deploy key GitHub en lecture seule
- [ ] Dépôt cloné dans `/srv/<SERVER_ID>/apps/`
- [ ] Répertoires `data`, `stacks`, `secrets`, `backups` séparés
- [ ] `.env` installé root:root en `600`
- [ ] Volume SQLite appartenant à UID/GID `10001`
- [ ] Compose validé
- [ ] Image construite
- [ ] Bot connecté à Discord
- [ ] Base initialisée depuis la version déployée
- [ ] `guild bootstrap` exécuté
- [ ] Catalog Sync exécuté
- [ ] Base historique sauvegardée avec l’API SQLite
- [ ] Bot arrêté avant migration
- [ ] Sauvegarde pré-migration créée et vérifiée
- [ ] Audit `matched/unmatched` validé
- [ ] Migration ciblée transactionnelle effectuée
- [ ] `integrity_check` et `foreign_key_check` OK
- [ ] Sauvegarde post-migration créée
- [ ] Base source temporaire supprimée
- [ ] Bot redémarré sans erreur
- [ ] Catalog Sync final validé
- [ ] Progression des catalogues confirmée

---

**Document anonymisé.** Aucun nom de personne, hostname réel, adresse IP, URL privée, token, mot de passe ou chemin local nominatif n’est nécessaire pour reproduire cette procédure.
