# Claviger

Claviger est un bot Discord développé en Python pour automatiser la gestion d'accès, de préférences et de rôles à partir de workflows contrôlés par le serveur.

Le projet est né d'un besoin concret : permettre aux utilisateurs de gérer eux-mêmes certains de leurs accès Discord sans transformer le bot en simple couche de commandes impératives.

Claviger repose sur une logique de réconciliation :

```text
État actuel
    +
Configuration du serveur
    +
Choix utilisateur
    ↓
État désiré
    ↓
Plan de modifications
    ↓
Prévalidation
    ↓
Exécution
```

L'objectif est de conserver une architecture modulaire, testable et réutilisable, capable de servir plusieurs serveurs Discord sans dupliquer la logique métier, puis d'exposer progressivement les mêmes capacités à d'autres interfaces : administration Web, outils IA et automatisations.

---

## État du projet

| Version | État | Objectif |
|---|---|---|
| **V1.0** | Déployée | Gestion des rôles, catalogues et questionnaires Discord |
| **V1.1** | En développement | Runtime multi-guild, configuration par serveur, reporting, généricité et robustesse |
| **V1.2** | Planifiée | Onboarding des nouveaux membres |
| **V1.3** | Planifiée | Administration Web et outils de modération |
| **Long terme** | Exploration | IA conversationnelle, tools et comportements agentiques |

La V1.0 est déployée sur un serveur Linux via Docker.

La V1.1 est développée sur `develop` dans un environnement Discord distinct de la production. Elle ne constitue pas une réécriture : chaque évolution est introduite par petites tranches testées et conservant les comportements déjà validés.

---

# Principes d'architecture

Claviger sépare volontairement :

```text
Application Discord
≠
Serveur Discord
≠
Configuration persistante
≠
Interface utilisateur
```

L'application possède une identité et une base SQLite communes.

Chaque serveur possède ensuite son propre état runtime, sa propre configuration ADMIN, ses propres catalogues et sa propre surface de commandes.

Le principe fondamental est :

```text
1 application Discord
    ↓
1 base SQLite
    ↓
N serveurs Discord
```

Une nouvelle guild ne crée donc jamais une nouvelle base.

---

# Runtime multi-guild — V1.1

Le runtime V1.1 n'est plus construit autour d'un serveur Discord principal.

Le démarrage est désormais application-scoped :

```text
Discord application
    ↓
Application identity
    ↓
Database status
    ↓
Database ownership
    ↓
Application runtime ready
```

Puis chaque serveur est configuré indépendamment :

```text
Discord guild
    ↓
Guild identity
    ↓
Guild configuration readiness
    ↓
Command tree
    ↓
Per-guild synchronization
    ↓
Guild runtime state
```

Les états sont stockés séparément dans un registre runtime par `guild_id`.

Chaque guild conserve notamment :

- son identité Discord locale ;
- son état de configuration ;
- sa signature d'arbre de commandes.

Cette séparation empêche une guild configurée d'influencer la readiness ou les commandes d'une autre.

---

## Cycle de vie Discord

`setup_hook()` prépare uniquement l'état applicatif :

- validation de l'identité du bot ;
- résolution de l'identité de l'application ;
- état de la base ;
- validation de l'ownership.

Le travail dépendant des serveurs est déclenché ensuite par les événements Discord :

```text
on_ready
→ configure les guilds actuellement disponibles

on_guild_join
→ configure une nouvelle guild rejointe pendant l'exécution

on_guild_available
→ reconfigure une guild redevenue disponible

on_guild_unavailable
→ invalide temporairement son état runtime

on_guild_remove
→ supprime son état runtime et son arbre local
```

Des locks dédiés empêchent deux événements Discord concurrents de reconfigurer simultanément la même guild.

---

# Identité Discord

L'identité de l'application et celle d'une guild sont volontairement séparées.

```text
DiscordApplicationIdentity
├── application_id
├── application_name
├── bot_user_id
└── admin_command_name
```

```text
DiscordGuildIdentity
├── guild_id
└── bot_display_name
```

Cette distinction est importante car le même bot peut notamment porter un nom d'affichage différent selon le serveur.

Une ancienne identité combinée peut encore subsister temporairement dans le code comme compatibilité de migration interne. Elle n'est plus le modèle cible du runtime.

---

# Base de données et ownership

Claviger utilise SQLite avec `aiosqlite`.

Le schéma est versionné avec :

```text
PRAGMA user_version
```

Les migrations sont explicites et appliquées successivement jusqu'à la version courante.

La base appartient à l'application Discord, pas à une guild.

Un ownership applicatif protège donc le runtime contre l'utilisation accidentelle d'une base appartenant à une autre application.

```text
DB absente
→ initialize

DB historique
→ migrate

DB READY mais non liée
→ bind

DB READY + bonne application
→ opérationnelle

DB READY + autre application
→ fail closed
```

Une erreur d'ownership bloque le runtime avant toute configuration dépendant d'une guild.

---

# Readiness par guild

Une base applicative READY ne signifie pas qu'un serveur est configuré.

Claviger distingue notamment :

```text
READY

ADMIN_CONFIGURATION_MISSING

ADMIN_CONFIGURATION_INCOMPLETE
```

L'absence de configuration pour une guild est un état normal lorsqu'un bot vient d'être invité sur un nouveau serveur.

```text
Application DB READY
├── Guild A : ADMIN complète
│   → runtime normal
│
├── Guild B : aucune config
│   → mode configuration
│
└── Guild C : config partielle
    → mode configuration
```

Les workflows normaux ne sont exposés que si :

```text
database_operational
AND
guild_ready
```

---

# Surface de commandes par guild

La surface de commandes est construite indépendamment pour chaque serveur.

Une guild prête peut exposer :

```text
/say
/membre
/noctis
/{bot} ...
```

Une guild non configurée reste volontairement en surface réduite :

```text
/{bot} database ...
/{bot} restart
/{bot} config-server
```

Le salon ADMIN constitue une restriction de contexte, pas une autorisation :
les contrôles owner / rôles de confiance restent indépendants.

---

# Configuration ADMIN par serveur

Elle ne reçoit pas automatiquement `/membre`, `/noctis` ou les groupes d'administration complets simplement parce qu'une autre guild utilise déjà la même application.

Le nom du groupe administratif est dérivé dynamiquement de l'application.

Exemples :

```text
/experimentum config-server
/claviger config-server
```
`config-server` n'est volontairement jamais une commande racine globale.

Lorsqu'une guild est READY, les commandes administratives normales sont
restreintes au `command_channel_id` persisté dans sa configuration ADMIN.

Les commandes de récupération restent volontairement utilisables hors de ce
salon afin d'éviter tout verrouillage administratif :

```text
/{bot} database ...
/{bot} restart
/{bot} config-server

---

# Configuration ADMIN par serveur

Chaque guild peut posséder une structure ADMIN persistée en SQLite.

```text
GuildAdminConfiguration
├── guild_id
├── category_id
├── command_channel_id
├── activity_forum_id
└── error_forum_id
```

Le pipeline est :

```text
Discord guild
    ↓
/{bot} config-server
    ↓
ADMIN discovery
    ↓
Reconciliation
    ↓
Provisioning
    ↓
Guild ADMIN configuration in SQLite
```

---

## Discovery

La découverte observe les structures Discord compatibles sans mutation.

Avant qu'une configuration ne soit persistée, les noms peuvent servir d'indice de découverte.

Une fois la configuration enregistrée, les IDs Discord deviennent l'identité de référence.

Le système vérifie notamment :

- la présence d'une catégorie ADMIN candidate ;
- sa visibilité ;
- les permissions effectives du bot ;
- les salons texte disponibles ;
- les forums disponibles ;
- la correspondance avec une configuration déjà persistée.

---

## Reconciliation

La réconciliation choisit une décision explicite :

```text
KEEP
CREATE
COMPLETE
IMPORT
NEEDS_CHOICE
```

### KEEP

La configuration persistée correspond toujours à Discord.

Aucune mutation n'est nécessaire.

### CREATE

Aucune structure ADMIN n'existe.

Claviger peut créer une structure privée complète :

```text
Claviger Admin
├── commands
├── activity
└── errors
```

Les IDs créés sont ensuite persistés.

### COMPLETE

Une structure sélectionnée existe mais elle est incomplète ou nécessite une réparation sûre.

Claviger peut notamment :

- compléter des types de salons manquants ;
- réparer les permissions nécessaires ;
- recréer une destination configurée disparue.

Il ne remplace pas arbitrairement une structure existante.

### IMPORT

Une structure compatible existe déjà mais sa sémantique n'est pas encore entièrement persistée.

Claviger ne devine pas automatiquement quel forum correspond à l'activité ou aux erreurs.

La sélection explicite reste nécessaire avant l'import persistant.

### NEEDS_CHOICE

Plusieurs structures candidates existent, ou la situation est ambiguë.

Aucune déduction silencieuse n'est faite.

Un choix humain est obligatoire.

---

## Principe fail-closed

`config-server` refuse de configurer un serveur lorsque la base applicative n'est pas dans un état sûr.

```text
DB non READY
→ /{bot} database status

DB READY mais ownership absent
→ /{bot} database bind
→ /{bot} restart

DB READY + ownership valide
→ config-server autorisé
```

La commande est actuellement réservée au propriétaire de la guild.

---

# Reporting et observabilité

Le reporting est désormais routé par guild à partir de sa configuration ADMIN persistée.

```text
ReportEvent
    ↓
guild_id
    ↓
GuildAdminConfiguration
    ↓
Destination Discord
```

Les événements normaux vont vers le forum d'activité :

```text
INFO
→ activity_forum_id
```

Les incidents vont vers le forum d'erreurs :

```text
WARNING
ERROR
CRITICAL
→ error_forum_id
```

Le logger Python reste application-wide et est enregistré indépendamment du reporter Discord.

Ainsi, une erreur de routage Discord ou de lecture de configuration ne supprime pas la trace locale de l'événement.

Lorsqu'une configuration ADMIN devient exploitable pour la première fois,
Claviger émet `admin.configuration.activated` comme premier événement `INFO`
dans le forum d'activité nouvellement configuré.

Le reporting Discord refuse de router un événement sans `guild_id` ou sans destination exploitable.

---

# Catalogues Discord

Claviger synchronise actuellement deux catalogues runtime historiques :

```text
member_interests
adult_accesses
```

Ils sont encore construits explicitement par le `CatalogRegistry`.

La cible V1.1 est de faire évoluer cette logique vers des définitions de workflows/catalogues configurées et persistées plutôt que multiplier les implémentations métier dédiées.

---

## Découverte rôle ↔ salon

Un rôle n'entre pas dans un catalogue uniquement parce que son nom correspond à un préfixe.

Le mapping doit également être exploitable.

```text
Discord roles / channels
    ↓
Role/channel discovery
    ↓
Prefix policy
    +
Exactly one explicit channel mapping
    ↓
Valid catalog candidate
```

Pour chaque rôle candidat :

- aucun salon explicite → mapping manquant ;
- exactement un salon explicite → mapping valide ;
- plusieurs salons explicites → mapping ambigu.

Un rôle au mapping manquant ou ambigu n'est donc pas créé comme nouvelle entrée valide du catalogue.

Cette règle évite qu'une simple convention de nommage produise automatiquement une configuration incorrecte.

---

# Synchronisation des catalogues

La synchronisation compare Discord avec l'état persistant :

```text
État Discord
    ↓
Snapshot découvert
    ↓
Plan de synchronisation
    ↓
Transaction SQLite
```

Elle distingue notamment :

- créations ;
- rafraîchissements ;
- changements d'état ;
- warnings de mapping ;
- ressources disparues.

Les métadonnées métier configurées manuellement sont préservées lorsque seules les données Discord observées évoluent.

Une erreur pendant la transaction entraîne un rollback SQLite plutôt qu'un état partiellement persisté.

---

# Workflows utilisateur actuels

## Centres d'intérêt

La commande publique :

```text
/membre
```

permet actuellement de gérer les centres d'intérêt.

Le workflow :

- restaure les sélections actuelles ;
- génère les choix depuis le catalogue ;
- calcule les rôles à ajouter et retirer ;
- préserve les rôles hors périmètre ;
- exécute les mutations uniquement après validation.

---

## Accès adultes

La commande historique :

```text
/noctis
```

gère actuellement les accès adultes.

Le nom correspond au serveur historique pour lequel Claviger a été créé.

La logique interne évolue progressivement vers des concepts plus génériques.

La V1 distingue notamment les conventions :

```text
access-no-ia-theme
access-ia-theme
```

La préférence IA est additive.

```text
Thème sélectionné
IA désactivée

→ access-no-ia-theme
```

Avec l'option IA activée :

```text
Thème sélectionné
IA activée

→ access-no-ia-theme
→ access-ia-theme
→ option-ia
```

---

# Cible V1.1 — workflows configurables et questionnaire générique

Cette partie décrit l'architecture cible de fin de V1.1. Elle n'est pas encore entièrement implémentée.

```text
Discord categories / roles / channels
    ↓
Discovery
    ↓
Role ↔ channel mapping
    ↓
Configured workflow / catalog definition
    ↓
SQLite catalog
    ↓
Generic questionnaire workflow
    ↓
Generic reusable modal
        ├── one stage when sufficient
        └── second stage only when complementary choices exist
    ↓
Complete user selection
    ↓
Planner
    ↓
Preflight
    ↓
Execution
```

Le but est que :

```text
/membre
/noctis
/futur access
```

deviennent des façades ou configurations de workflow plutôt que trois moteurs de questionnaire indépendants.

---

## Questionnaire adulte multi-étapes

Le parcours cible reste adaptatif :

```text
Commande adulte
    ↓
Choix principaux + préférence IA
    ↓
Accès complémentaires nécessaires ?
    ├── Non → validation finale
    └── Oui → seconde modal
                ↓
             validation finale
```

La seconde étape ne doit exister que lorsqu'elle contient réellement des choix utiles.

Aucune mutation Discord ne doit avoir lieu entre les étapes.

Le planner reçoit uniquement la sélection complète et finalisée.

---

# Réconciliation des rôles

Les workflows ne modifient pas directement Discord depuis les composants UI.

```text
Questionnaire
    ↓
Planner
    ↓
Execution plan
    ↓
Preflight
    ↓
Executor
```

## Questionnaire

Construit les choix disponibles et restaure les sélections existantes.

## Planner

Compare :

- état Discord actuel ;
- sélection utilisateur ;
- règles métier.

Il produit un plan déterministe d'ajouts et de suppressions.

Le planner ne modifie pas Discord.

## Preflight

Avant la première mutation, le système valide notamment :

- existence des rôles ;
- manageability ;
- rôles administrés par Discord ;
- hiérarchie ;
- cohérence de la cible.

## Executor

Applique uniquement le plan prévalidé.

Les rôles hors périmètre du workflow sont préservés.

## Coordinator

Orchestre les différentes étapes sans placer la logique métier dans les commandes Discord.

---

# Sécurité

Claviger applique plusieurs principes de sécurité structurants.

## Fail closed

Lorsqu'un état est ambigu, invalide ou non vérifiable, le bot refuse de deviner.

Ce principe s'applique notamment :

- à l'ownership de la DB ;
- à la readiness d'une guild ;
- au mapping rôle ↔ salon ;
- à la configuration ADMIN ;
- aux permissions ;
- aux mutations Discord.

---

## Domaine de responsabilité limité

Un workflow ne modifie que les rôles faisant explicitement partie de son domaine.

Les rôles administratifs, honorifiques ou appartenant à d'autres systèmes restent intacts.

---

## Prévalidation

Les effets de bord Discord sont précédés d'un preflight complet lorsque le workflow le permet.

---

## Permissions Discord et autorisation applicative

Deux concepts sont distingués :

```text
Permissions Discord
→ ce que Claviger peut techniquement faire

Policy Claviger
→ ce qu'un utilisateur est autorisé à demander
```

Le fait qu'un utilisateur puisse voir ou écrire dans un salon administratif ne remplace jamais les contrôles applicatifs.

---

## Secrets

Les secrets runtime restent hors du dépôt.

Le fichier :

```text
.env.example
```

documente uniquement les variables attendues.

Les fichiers `.env.*` locaux et les bases runtime ne doivent pas être versionnés.

---

## Conteneur non-root

L'image Docker de production utilise un utilisateur dédié non privilégié.

---

# Succumbrae et fallback historique

Claviger a été créé à l'origine pour une guild spécifique.

Cette origine subsiste volontairement sous la forme d'un fallback historique de policy/bootstrap.

Conceptuellement :

```text
Succumbrae
→ fallback historique
→ compatibilité / recovery policy

mais PAS

Succumbrae
→ guild runtime privilégiée
```

Le runtime multi-guild ne possède plus de serveur principal.

La variable historique `DISCORD_GUILD_ID` peut encore être utilisée comme ancre de fallback de policy tant que cette compatibilité n'a pas été remplacée.

Elle ne sélectionne plus la guild runtime de l'application.

---

# Signatures d'arbre et restart

Chaque guild possède sa propre signature déterministe d'arbre de commandes.

Lors d'un restart interne :

```text
Guild A signature
Guild B signature
Guild C signature
    ↓
RuntimeRestartRequest
```

Après reconstruction, Claviger compare chaque arbre indépendamment.

Si l'arbre d'une guild est inchangé, une synchronisation Discord inutile peut être évitée.

Le restart reste une opération applicative propre.

Il ne donne pas au bot un accès au socket Docker ni à l'hôte.

---

# Tests

Claviger dispose de plus de **460 tests automatisés**.

Ils couvrent notamment :

- modèles métier ;
- identité Discord ;
- politiques de guild ;
- repositories SQLite ;
- migrations ;
- ownership de base ;
- discovery ADMIN ;
- reconciliation ADMIN ;
- provisioning ADMIN ;
- readiness par guild ;
- runtime multi-guild ;
- isolation entre guilds ;
- lifecycle Discord ;
- signatures de command tree ;
- catalogues ;
- mapping rôle ↔ salon ;
- questionnaires ;
- planners ;
- executors ;
- coordinators ;
- autorisations ;
- reporting ;
- routage reporting par guild ;
- commandes Discord ;
- interfaces Discord ;
- composition globale du bot.

Le projet utilise volontairement les tests comme outil de conception.

Le workflow habituel est :

```text
Modification cohérente
    ↓
Tests ciblés
    ↓
Ruff
    ↓
Suite complète
    ↓
Test Discord réel si nécessaire
    ↓
Commit
```

Une tranche n'est pas considérée terminée uniquement parce que le code semble correct à la lecture.

---

# Environnements Development / Production

Le développement et la production utilisent des environnements Discord séparés.

```text
Production
├── application Discord PROD
├── guild(s) de production
├── base SQLite PROD
└── configuration PROD

Development
├── application Discord DEV
├── guild(s) de test
├── base SQLite DEV
└── configuration DEV
```

Cela permet notamment de tester :

- bootstrap sur serveur vierge ;
- nouvelle guild rejointe à chaud ;
- readiness indépendante ;
- commandes différentes selon la guild ;
- provisioning ADMIN ;
- config-server ;
- mapping rôle ↔ salon ;
- migrations ;
- reporting ;
- erreurs de permissions ;
- scénarios de convergence.

Les bases DEV et PROD ne doivent jamais être interchangeées comme mécanisme de déploiement.

---

# V1.1 — déjà implémenté

La consolidation V1.1 a déjà introduit plusieurs changements structurants.

### Runtime multi-guild

- état runtime par guild ;
- lifecycle event-driven ;
- isolation de la readiness ;
- isolation des command trees ;
- locks par guild ;
- join/available/unavailable/remove gérés indépendamment.

### Identité application / guild

- identité Discord applicative séparée ;
- identité locale de guild séparée.

### Ownership de base

- DB liée à l'application ;
- mismatch fail-closed ;
- aucune initialisation par guild.

### Configuration ADMIN

- discovery ;
- reconciliation ;
- provisioning ;
- persistence SQLite ;
- `/{bot} config-server`.

### Readiness par guild

- `READY` ;
- `ADMIN_CONFIGURATION_MISSING` ;
- `ADMIN_CONFIGURATION_INCOMPLETE`.

### Reporting par guild

- activité vers le forum activité ;
- incidents vers le forum erreurs ;
- routage à partir de la DB ;
- Python logging indépendant.

### Isolation multi-guild

Les tests couvrent explicitement :

```text
Guild A READY
Guild B non configurée
Guild C rejointe pendant le runtime
```

sans contamination mutuelle.

---

# V1.1 — reste à réaliser

La roadmap de fin de V1.1 comprend encore principalement :

### Workflows/catalogues configurables

Remplacer progressivement les deux définitions runtime historiques :

```text
member_interests
adult_accesses
```

par des définitions persistées et génériques.

### Questionnaire générique

Réutiliser un même moteur UI/workflow pour plusieurs usages.

### Parcours adulte complémentaire

Ouvrir une seconde modal uniquement lorsqu'une étape complémentaire est réellement nécessaire.

### UI config-server

Ajouter les composants Discord permettant de résoudre explicitement les cas :

```text
IMPORT
NEEDS_CHOICE
```

sans inférence sémantique.

### Last Known Good

Préparer un snapshot par guild pour certaines lectures sûres lorsque SQLite devient temporairement indisponible.

Les mutations persistantes resteront fail-closed.

### Nettoyage des compatibilités

Supprimer les éléments temporaires une fois leurs remplaçants validés :

- identité runtime combinée historique ;
- anciens resolvers ;
- anciens fallbacks inutiles ;
- dépendances ENV devenues obsolètes ;
- noms et wrappers de compatibilité.

### Audit final

Avant la V1.1 :

- audit architecture ;
- audit sécurité ;
- audit logging ;
- audit documentation ;
- campagne de défaillances ;
- smoke tests sur plusieurs guilds.

### CI/CD

La CI et le déploiement contrôlé doivent être ajoutés après stabilisation fonctionnelle.

---

# Last Known Good — cible

SQLite reste la source persistante principale.

La V1.1 prévoit un snapshot de dernier état valide par guild :

```text
guild_id
    ↓
Last Known Good Snapshot
```

Ce mécanisme doit permettre certaines lectures sûres en mode dégradé.

Il ne doit jamais devenir une seconde source de vérité modifiable.

Le snapshot doit être :

- read-only côté recovery ;
- écrit atomiquement ;
- mis à jour uniquement après validation d'un état DB cohérent ;
- versionné ;
- limité aux données réellement nécessaires.

Toute mutation persistante doit rester bloquée si la base principale est indisponible.

---

# Robustesse attendue avant V1.1

Les scénarios de défaillance à tester incluent notamment :

- catégorie ADMIN supprimée ;
- salon de commandes supprimé ;
- forum activité supprimé ;
- forum erreurs supprimé ;
- permissions du bot retirées ;
- visibilité `@everyone` réouverte ;
- rôle référencé supprimé ;
- mapping rôle ↔ salon devenu ambigu ;
- guild temporairement indisponible ;
- bot invité sur une nouvelle guild ;
- mutation Discord partiellement réussie ;
- DB absente ;
- DB corrompue ;
- DB indisponible ;
- DB trop récente ;
- DB non liée ;
- DB liée à une autre application ;
- reconfiguration d'une guild sans impact sur les autres.

---

# V1.2 — Onboarding

La V1.2 doit introduire le parcours d'arrivée automatique d'un nouveau membre.

```text
Nouvel utilisateur
    ↓
Message privé de bienvenue
    ↓
Instructions d'arrivée
```

En cas d'impossibilité d'envoyer le MP :

```text
Échec du message privé
    ↓
Fallback public neutre
    ↓
Reporting
```

Cette évolution sera construite sur le runtime multi-guild et les services consolidés de la V1.1.

---

# V1.3 — Administration Web et modération

La V1.3 doit introduire une interface d'administration plus complète.

L'objectif est de piloter les mêmes services métier sans accéder directement à SQLite.

```text
Discord UI ─┐
Web Admin ──┼→ Application services → Repositories → SQLite
Future AI ──┘
```

Exemples :

```text
Serveurs
├── sélectionner une guild
├── consulter son état
└── inspecter sa configuration

Policies
├── rôles fonctionnels
├── permissions
├── salons
└── options

Catalogues
├── labels
├── descriptions
├── emojis
├── ordre
└── activation

Modération
├── rôles fonctionnels
├── commandes dédiées
└── reporting
```

---

# Évolution IA

L'intégration d'une intelligence artificielle n'est pas le point de départ de Claviger.

Le projet cherche d'abord à fournir des capacités déterministes, testables et sécurisées.

À terme :

```text
Utilisateur
    ↓
Interface conversationnelle
    ↓
LLM / Agent
    ↓
Tools Claviger
    ↓
Services métier existants
    ↓
Discord / autres ressources
```

L'IA devra utiliser les mêmes services et garde-fous que les interfaces humaines.

Elle ne doit pas contourner les règles métier ni posséder une implémentation parallèle des capacités Discord.

---

# Architecture générale

```text
Discord UI ─┐
Web Admin ──┼→ Application / Domain Services
Future AI ──┘
                    ↓
            Repositories / Adapters
                    ↓
                  SQLite
```

Discord est une interface et une source d'état externe importante.

Il n'est pas le cœur métier du système.

Cette séparation vise à :

- isoler les effets de bord ;
- tester la logique hors Discord ;
- réutiliser les services ;
- faire évoluer les interfaces sans réécrire le domaine ;
- limiter les couplages ;
- garder des responsabilités compréhensibles.

---

# Technologies

Le projet utilise principalement :

- **Python 3.12**
- **discord.py**
- **SQLite**
- **aiosqlite**
- **python-dotenv**
- **pytest**
- **pytest-asyncio**
- **Ruff**
- **Docker**

Le projet utilise une structure Python `src/`.

---

# Déploiement

La production utilise une image basée sur :

```text
python:3.12-slim
```

Le conteneur :

- installe le package applicatif ;
- utilise un utilisateur non-root ;
- reçoit sa configuration depuis l'environnement ;
- conserve les données runtime hors de l'image.

Le bot ne doit pas recevoir d'accès direct au socket Docker pour gérer son propre restart.

Le déploiement contrôlé et la CI/CD font partie des étapes finales de consolidation.

---

# Branches

Le workflow utilise principalement :

```text
main
→ version stable

develop
→ développement de la prochaine version

deployment branch
→ état utilisé pour un déploiement contrôlé
```

Les évolutions sont testées avant intégration sur la branche stable.

---

# Documentation technique

Le dépôt contient une documentation complémentaire dans :

```text
documentations/
```

Elle comprend notamment :

- cadrage initial ;
- prompts maîtres de continuité ;
- rétrospectives des interventions humaines ;
- audits d'architecture ;
- documentation technique ;
- sécurité / logs / observabilité ;
- déploiement.

Cette documentation fait partie du projet au même titre que le code.

Elle sert notamment à conserver les décisions d'architecture et à éviter qu'un changement de session ou d'outil perde le contexte technique accumulé.

---

# Développement assisté par intelligence artificielle

Claviger est développé avec une assistance IA importante et volontairement documentée.

L'IA intervient notamment pour :

- proposer des implémentations ;
- générer du code ;
- produire ou renforcer les tests ;
- analyser des erreurs ;
- challenger l'architecture ;
- identifier des cas limites ;
- relire le code ;
- documenter les décisions ;
- préparer des audits.

Cela ne signifie pas que le projet est développé de manière autonome.

Le workflow réel est davantage :

```text
Besoin / problème réel
    ↓
Direction humaine
    ↓
Discussion / challenge
    ↓
Proposition assistée
    ↓
Analyse humaine
    ↓
Implémentation
    ↓
Tests
    ↓
Observation du comportement réel
    ↓
Correction / arbitrage
    ↓
Validation
```

L'IA peut produire une part importante du code.

La responsabilité de production reste néanmoins humaine :

- définition du besoin ;
- architecture ;
- contraintes métier ;
- acceptation ou rejet des propositions ;
- niveau de risque acceptable ;
- validation fonctionnelle ;
- décision de commit et de livraison.

Le rôle du développeur évolue donc progressivement d'une production manuelle de chaque ligne vers davantage de conception, de contrôle, de validation et de direction technique, sans abandonner la compréhension du système.

---

# Principes de développement

Claviger suit quelques règles simples :

- éviter le code jetable ;
- documenter les responsabilités et contrats importants ;
- séparer les imports par responsabilité dans les fichiers complexes ;
- commenter le **pourquoi** plutôt que paraphraser le code ;
- préférer un fichier complet à une série de micro-patchs lorsqu'une modification touche plusieurs zones corrélées ;
- privilégier les services réutilisables lorsqu'une abstraction est réellement justifiée ;
- ne pas généraliser sans besoin concret ;
- séparer logique métier et effets de bord ;
- privilégier les IDs Discord comme identité persistante ;
- conserver les noms comme données humaines ou indices de découverte ;
- échouer explicitement plutôt que deviner ;
- garder les guilds isolées ;
- tester chaque évolution ;
- conserver les changements en petites tranches cohérentes ;
- ne supprimer une compatibilité qu'après validation de son remplacement ;
- améliorer progressivement le système plutôt que lancer des refactorisations globales.

---

# Pourquoi « Claviger » ?

Le nom provient de l'identité du serveur pour lequel le projet a été initialement développé.

Le projet conserve volontairement une partie de cet héritage dans certains noms publics et dans un fallback historique.

Son architecture n'est cependant plus limitée à ce serveur.

Claviger est aujourd'hui à la fois :

- un bot Discord réellement utilisé ;
- un projet multi-guild ;
- un laboratoire d'architecture logicielle ;
- un terrain d'expérimentation autour de l'automatisation ;
- un exemple documenté de développement logiciel fortement assisté par intelligence artificielle.
