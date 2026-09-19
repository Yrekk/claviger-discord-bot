# Claviger

## Checkpoint V1.1 — 19 septembre 2026

La branche active de travail est `feature/v11-ai-config-server`, destinée à être
réintégrée dans `refactor/generic-workflows-v11` après validation explicite.

Le schéma SQLite courant est **V12**.

Les tranches suivantes sont maintenant implémentées et validées fonctionnellement
sur l'environnement Discord de laboratoire :

- configuration ADMIN multi-guild ;
- configuration IA globale par guild ;
- ownership unique de la question IA ;
- configuration générique des workflows avec réservations de rôles ;
- annotation des structures Discord déjà utilisées ;
- commandes runtime reconstruites depuis les workflows persistés ;
- moteur de questionnaire générique ;
- synchronisation générique des catalogues depuis Discord ;
- diagnostics administratifs `config scan`, `roles scan` et `catalog scan`.

La prochaine tranche porte sur **l'administration des métadonnées de catalogue** :
permettre de synchroniser volontairement les entrées puis de compléter les
`label` / `description` nécessaires au questionnaire, sur le nouveau backend
générique. Le smoke questionnaire reprendra immédiatement après cette tranche.

La roadmap de référence est :

```text
documentations/V1.1/05_ROADMAP_RESTANT_V1_1.md
```


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
| **V1.1** | En développement — socle stabilisé | Runtime multi-guild, configuration par serveur, reporting, généricité et robustesse |
| **V1.2** | Planifiée | Onboarding des nouveaux membres et fonctionnalités sociales / fun |
| **V1.3** | Planifiée | Administration Web et outils de modération |
| **Long terme** | Exploration | IA conversationnelle, tools et comportements agentiques |

La V1.0 est déployée sur un serveur Linux via Docker.

La V1.1 est actuellement développée sur la feature
`feature/v11-ai-config-server`, au-dessus de
`refactor/generic-workflows-v11`. Elle sera intégrée dans `develop` seulement
après fermeture fonctionnelle et validation complète.

### Checkpoint V1.1 — 19 septembre 2026

Le socle multi-guild, la configuration ADMIN, le reporting par guild, la
configuration générique des workflows et le runtime questionnaire générique sont
implémentés.

Le runtime sait désormais :

- reconstruire les commandes de workflow persistées au démarrage ;
- synchroniser les cibles catalogue depuis l'état Discord réel ;
- restaurer l'état des rôles d'un membre ;
- appliquer les variantes `base`, `no_ai` et `ai` ;
- lire une préférence IA globale de guild ;
- limiter la question IA à un unique workflow propriétaire ;
- planifier les mutations avant exécution ;
- prévalider tous les rôles avant la première mutation ;
- préserver les rôles hors périmètre du workflow.

Les outils de diagnostic V1.1 sont également en place :

- `/{bot} config scan` : état global, workflows configurés et structures
  potentielles détectées ;
- `/{bot} roles scan` : classification des rôles et anomalies de patterns ;
- `/{bot} catalog scan` : structure, commande, rôle principal, mappings,
  métadonnées et anomalies par workflow/catalogue.

Le prochain chantier est l'administration des métadonnées de catalogue, avant
de reprendre les smoke tests des questionnaires sur les deux guilds DEV.

La roadmap opérationnelle du reste de la V1.1 est maintenue dans :

```text
documentations/V1.1/05_ROADMAP_RESTANT_V1_1.md
```


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
/adult
/{bot} ...
```

Une guild non configurée reste volontairement en surface réduite :

```text
/{bot} database ...
/{bot} restart
/{bot} config-server
/{bot} config scan
```

Le salon ADMIN constitue une restriction de contexte, pas une autorisation :
les contrôles owner / rôles de confiance restent indépendants.

---

# Configuration ADMIN par serveur

Elle ne reçoit pas automatiquement les commandes de workflows persistés d'une autre guild ni les groupes d'administration complets simplement parce qu'une autre guild utilise déjà la même application.

Le nom du groupe administratif est dérivé dynamiquement de l'application.

Exemples :

```text
/experimentum config-server
/claviger config-server
```

`config-server` n'est volontairement jamais une commande racine globale.

Lorsqu'une guild est READY, les commandes administratives normales sont restreintes au `command_channel_id` persisté dans sa configuration ADMIN.

Les commandes de récupération restent volontairement utilisables hors de ce salon afin d'éviter tout verrouillage administratif :

```text
/{bot} database ...
/{bot} restart
/{bot} config-server
/{bot} config scan
```

---

## Diagnostics administratifs

Les diagnostics sont read-only : ils observent Discord et SQLite sans effectuer
de mutation.

### `/{application-root} config scan`

Expose notamment :

- état et version de la base SQLite ;
- ownership applicatif ;
- état de la configuration ADMIN ;
- état de l'IA globale et rôle IA ;
- workflow propriétaire de la question IA ;
- compteurs déclaratifs ;
- workflows configurés, avec commande et catégorie ;
- **workflows potentiels détectés par la discovery**, avec leurs salons protégés
  et interactifs ;
- indication des structures déjà liées à un workflow ou encore disponibles.

Le rendu Discord privilégie les noms et états humains. Les IDs techniques ne sont
pas affichés dans le diagnostic normal.

`config scan` conserve un comportement de recovery :

```text
ADMIN sain
→ commande autorisée uniquement dans le salon ADMIN configuré

ADMIN absent / incomplet / en drift
→ diagnostic utilisable pour permettre la réparation
```

### `/{application-root} roles scan`

Classe les rôles du serveur selon leur usage réel :

- rôle de l'application ;
- rôle IA global ;
- rôles principaux de workflows ;
- rôles catalogue configurés ;
- rôles manipulables hors workflows ;
- rôles non manipulables ;
- anomalies de pattern ou de mapping.

### `/{application-root} catalog scan`

Produit un diagnostic détaillé, séparé par workflow :

- validité de la structure ;
- commande persistée ;
- catégorie, salons de gestion et d'exécution ;
- rôle principal et salons explicitement visibles avec ce rôle ;
- ownership de la question IA ;
- pattern de catalogue ;
- rôles et salons détectés ;
- entrées BDD ;
- métadonnées complètes/incomplètes ;
- rôles non synchronisés ;
- rôles non manipulables ou mappings incohérents.

Les problèmes sont affichés par couche : **structure**, **commande** et
**catalogue**, afin d'éviter un statut générique ambigu.


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

La V1.1 utilise désormais un stockage générique :

```text
guild_catalogs
    ↓
guild_catalog_entries
    ↓
guild_catalog_entry_targets
```

Un catalogue est lié à un workflow par sa définition persistée. Les anciennes
tables spécialisées `guild_member_interests` et `guild_adult_accesses` ont été
migrées vers ce modèle lors du passage V10 → V11.

Les métadonnées humaines d'une entrée sont séparées de ses cibles Discord :

```text
entrée logique
├── label
├── description
├── emoji
└── targets
    ├── base
    ├── no_ai
    └── ai
```

La synchronisation automatique du runtime met à jour l'identité et la santé des
cibles Discord sans écraser les métadonnées humaines déjà configurées.

La prochaine tranche ajoute la surface d'administration permettant de compléter
les métadonnées manquantes sur ce backend générique.


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

# Workflows utilisateur V1.1

Les commandes utilisateur ne reposent plus sur des moteurs spécialisés codés en
dur. Chaque commande est reconstruite depuis un `guild_workflow` persisté.

Exemples actuellement utilisés sur le laboratoire :

```text
/membre
/adult
```

Le nom de commande, la catégorie, les salons, le rôle principal et les
catalogues sont des données de configuration.

---

# Runtime générique des questionnaires

Le pipeline V1.1 est maintenant implémenté :

```text
workflow persisté
    ↓
commande Discord reconstruite
    ↓
synchronisation du catalogue depuis Discord
    ↓
état courant du membre
    ↓
préférence IA globale de la guild
    ↓
questionnaire générique
    ↓
sélection complète
    ↓
planner
    ↓
preflight de tous les rôles
    ↓
mutations Discord
    ↓
reporting
```

## Préférence IA globale

La préférence IA appartient à la guild et est matérialisée par un rôle global.

Un seul workflow par guild peut être propriétaire de la question IA :

```text
guild_ai_questionnaire_owner
guild_id → workflow_key
```

Les autres workflows ne reposent jamais la question. Ils lisent simplement
l'état du rôle IA déjà attribué au membre.

Le cas standard visé est :

```text
/membre
→ questionnaire obligatoire d'entrée
→ pose la question IA
→ attribue éventuellement le rôle IA global

/adult
→ ne pose pas la question IA
→ lit le rôle IA global
→ choisit les variantes de catalogue correspondantes
```

## Variantes de cibles

Pour une entrée logique sélectionnée :

- `base` est indépendante de la préférence IA ;
- une paire `no_ai` / `ai` choisit la cible correspondant à l'état IA ;
- une cible `ai` seule n'est disponible que lorsque l'IA est active pour le
  membre ;
- une cible `no_ai` seule n'est disponible que lorsque l'IA est inactive.

Le changement de préférence conserve la sélection logique et remplace la cible
concrète appropriée au moment du planning.

## Interface Discord

Le questionnaire utilise les composants Discord natifs. Les choix visibles sont
capturés dans la soumission afin de détecter un formulaire devenu obsolète entre
son ouverture et sa validation.

Aucune mutation Discord n'a lieu avant la validation finale.


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

La suite exécutée pour cette tranche compte **488 tests réussis** (444 avant la migration V11).

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

La consolidation V1.1 comprend maintenant :

- runtime multi-guild et lifecycle event-driven ;
- identité application/guild séparée ;
- ownership SQLite applicatif ;
- readiness par guild ;
- ADMIN discovery/reconciliation/provisioning/persistence ;
- reporting activity/error par guild ;
- configuration IA globale ;
- ownership unique de la question IA ;
- migration SQLite V11 puis V12 ;
- configuration générique des workflows ;
- filtrage des rôles réservés et revalidation backend ;
- annotation des structures Discord déjà utilisées ;
- commandes runtime dynamiques issues des workflows persistés ;
- synchronisation générique des catalogues ;
- questionnaire générique avec planner/preflight/executor ;
- diagnostics `config scan`, `roles scan` et `catalog scan` ;
- réorganisation architecturale et tests en miroir.

Les tranches sont validées progressivement sur une application Discord DEV et
plusieurs guilds de test. La V1.1 n'est pas encore considérée fermée tant que les
métadonnées catalogue, les smoke questionnaires multi-guild, le recovery et le
déploiement contrôlé ne sont pas terminés.


# V1.1 — reste à réaliser

La source de reprise détaillée est :

```text
documentations/V1.1/05_ROADMAP_RESTANT_V1_1.md
```

Ordre actuel :

```text
1. Administration des métadonnées de catalogue
2. Smoke questionnaire Laboratorium
3. Smoke questionnaire seconde guild
4. Robustesse / recovery / snapshots
5. Audit architecture, sécurité et reporting
6. CI/CD et validation Linux
7. Smoke final V1.1
8. Documentation finale
9. Intégration feature → refactor → develop
10. Déploiement contrôlé sur Succumbrae
11. Validation production puis main
```

### Prochaine tranche — métadonnées de catalogue

Le backend sait déjà découvrir et synchroniser les entrées techniques. Il faut
maintenant fournir une surface admin moderne, construite sur ce même backend,
pour :

- déclencher explicitement une synchronisation si nécessaire ;
- lister les entrées incomplètes ;
- compléter au minimum `label` et `description` ;
- préserver les métadonnées existantes lors des refresh Discord ;
- rendre l'état visible immédiatement dans `catalog scan`.

L'objectif fonctionnel reprend l'ergonomie utile des anciens
`catalog sync` / `catalog next`, sans réintroduire l'ancien stockage
spécialisé.

### Smoke questionnaire

Le premier scénario de fermeture est volontairement construit autour de deux
workflows :

```text
/membre
→ propriétaire de la question IA
→ catalogue simple indépendant de l'IA

/adult
→ non propriétaire
→ base
→ paire no_ai / ai
→ ai-only
→ no-ai-only
→ cas de rôle non manipulable
```

Ce smoke doit prouver qu'un membre ayant choisi l'IA dans `/membre` obtient
ensuite les cibles IA appropriées dans `/adult`, sans que ce second workflow
repose ou modifie la préférence globale.

### Robustesse et intégration

Après les deux smokes guild :

- campagne de drift Discord ;
- échecs partiels de mutation ;
- DB absente, corrompue, indisponible ou trop récente ;
- snapshots / Last Known Good ;
- audit final ;
- CI/CD ;
- validation Linux ;
- intégration contrôlée puis déploiement.


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

Le déploiement contrôlé fait partie des étapes finales de consolidation après validation de `develop`.

---

# Branches

Le workflow utilise principalement :

```text
main
→ version stable

develop
→ branche d'intégration de la prochaine version

feature/v11-ai-config-server
→ feature active de fermeture fonctionnelle V1.1

refactor/generic-workflows-v11
→ branche d'intégration V1.1 avant develop

deploy/succumbrae
→ branche de déploiement contrôlé sur le serveur Linux
```

Les évolutions sont testées avant intégration sur `develop`, puis avant livraison sur la branche stable ou de déploiement appropriée.

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
- déploiement ;
- roadmap opérationnelle de fin de V1.1.

Pour la reprise de la V1.1, le document prioritaire est :

```text
documentations/V1.1/05_ROADMAP_RESTANT_V1_1.md
```

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

