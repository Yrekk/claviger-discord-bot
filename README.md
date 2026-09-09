# Claviger

Claviger est un bot Discord développé en Python pour automatiser la gestion d'accès, de préférences et de rôles à partir de workflows contrôlés par le serveur.

Le projet est né d'un besoin concret : permettre aux utilisateurs de gérer eux-mêmes certains de leurs accès Discord sans transformer le bot en simple couche de commandes impératives.

Claviger repose donc sur une logique de réconciliation :

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

L'objectif à long terme est de conserver cette architecture modulaire pour faire évoluer progressivement Claviger vers un outil d'administration Discord plus général, puis vers une plateforme capable d'intégrer des fonctions conversationnelles et agentiques.

---

## État du projet

| Version | État | Objectif |
|---|---|---|
| **V1.0** | Déployée | Gestion des rôles, catalogues et questionnaires Discord |
| **V1.1** | En développement | Consolidation, fiabilité, observabilité et sécurité |
| **V1.2** | Planifiée | Onboarding des nouveaux membres |
| **V1.3** | Planifiée | Administration Web et outils de modération |
| **Long terme** | Exploration | IA conversationnelle, outils et comportements agentiques |

La V1.0 est actuellement déployée sur un serveur Linux via Docker.

Le développement de la V1.1 est réalisé sur une branche dédiée et dans un environnement Discord de développement totalement séparé de la production.

---

# Fonctionnalités actuelles — V1.0

## Gestion des centres d'intérêt

La commande publique :

```text
/membre
```

permet à un utilisateur de sélectionner les centres d'intérêt auxquels il souhaite être associé.

Le questionnaire est généré à partir d'un catalogue synchronisé avec Discord.

Lors de sa validation, Claviger peut :

- attribuer le rôle de membre si nécessaire ;
- ajouter les rôles correspondant aux intérêts sélectionnés ;
- retirer les anciennes sélections décochées ;
- restaurer automatiquement l'état actuel lors de la réouverture du questionnaire ;
- préserver tous les rôles qui ne font pas partie du périmètre du workflow.

Un questionnaire peut donc être relancé plusieurs fois sans créer de doublons ou écraser des rôles extérieurs au système.

---

## Gestion des accès adultes

La commande :

```text
/noctis
```

permet actuellement de gérer des accès à des espaces réservés aux adultes.

Le nom de cette commande correspond au serveur pour lequel Claviger a été initialement développé.

La logique interne a vocation à devenir progressivement indépendante de ce vocabulaire spécifique.

La V1.0 distingue principalement des paires de rôles selon la convention :

```text
access-no-ia-theme
access-ia-theme
```

La première entrée représente l'accès classique au thème.

La seconde ajoute l'accès à la variante contenant également du contenu généré par intelligence artificielle.

La préférence IA est additive :

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

Le rôle global `option-ia` représente actuellement la préférence IA de l'utilisateur.

---

# Catalogues Discord

Claviger ne repose pas uniquement sur des noms de rôles codés en dur.

Les éléments configurables sont synchronisés dans une base SQLite.

Deux catalogues principaux existent actuellement :

```text
Member interests
Adult accesses
```

Chaque entrée peut notamment conserver :

- l'identifiant Discord du rôle ;
- son nom actuel ;
- une clé métier ;
- l'identifiant du salon associé ;
- son nom ;
- un label destiné à l'utilisateur ;
- une description ;
- un emoji ;
- un ordre d'affichage ;
- son état d'activation ;
- la présence réelle du rôle et du salon ;
- la validité du mapping ;
- la possibilité pour Claviger de manipuler le rôle.

L'identité Discord repose donc principalement sur les IDs plutôt que sur les noms visibles.

Un rôle peut être renommé sans nécessairement être interprété comme une nouvelle ressource.

---

# Synchronisation

La synchronisation des catalogues compare l'état observé sur Discord avec les données persistantes.

Elle distingue volontairement :

```text
État Discord
    ↓
Snapshot découvert
    ↓
Plan de synchronisation
    ↓
Transaction SQLite
```

Les catalogues membres et adultes sont synchronisés dans une opération coordonnée.

Une erreur pendant la synchronisation entraîne le rollback de la transaction concernée plutôt qu'un état partiellement écrit.

Les métadonnées configurées manuellement sont conservées lorsque les informations techniques Discord évoluent.

---

# Réconciliation des rôles

Claviger ne modifie pas directement les rôles à partir de l'interface utilisateur.

Les workflows suivent plusieurs étapes.

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

Construit les choix disponibles et restaure les sélections déjà présentes sur l'utilisateur.

## Planner

Compare :

- l'état Discord actuel ;
- les choix utilisateur ;
- les règles du workflow.

Il produit ensuite un plan déterministe d'ajouts et de suppressions.

Le planner ne modifie jamais Discord.

## Executor

Reçoit le plan final et valide les opérations avant la première mutation.

Il vérifie notamment :

- que les rôles existent toujours ;
- que Claviger peut les manipuler ;
- qu'ils ne sont pas administrés automatiquement par Discord ;
- qu'ils respectent la hiérarchie Discord ;
- que la cible est valide.

## Coordinator

Orchestre questionnaire, planification et exécution sans placer toute la logique métier dans les commandes Discord.

---

# Architecture

Le projet utilise une architecture modulaire par responsabilités.

```text
Discord
   ↓
Commands / UI
   ↓
Workflow Coordinators
   ↓
Domain Services
   ├── Questionnaire
   ├── Planner
   ├── Executor
   ├── Discovery
   └── Synchronization
   ↓
Repositories
   ↓
SQLite
```

Le reporting constitue une sortie transversale indépendante :

```text
Application
    ├── Discord
    ├── SQLite
    └── Reporting
```

Cette séparation vise plusieurs objectifs :

- isoler les effets de bord Discord ;
- faciliter les tests unitaires ;
- conserver la logique métier hors de l'UI ;
- pouvoir remplacer ou enrichir les interfaces plus tard ;
- éviter les dépendances inutiles entre modules ;
- préparer l'évolution du projet sans construire prématurément un framework générique.

---

# Base de données

Claviger utilise SQLite avec `aiosqlite`.

Le schéma est versionné avec :

```text
PRAGMA user_version
```

Les migrations sont explicites et exécutées dans l'ordre jusqu'à la version courante.

La V1.1 renforce également les tests de migration afin que les bases historiques utilisées dans les tests représentent réellement l'ensemble du schéma de leur version.

Cela permet de valider notamment :

```text
ancienne base
    ↓
migrations successives
    ↓
schéma courant
```

sans construire de faux états historiques partiels.

---

# Sécurité

Claviger applique plusieurs principes de sécurité dès la V1.

## Domaine de responsabilité limité

Un workflow ne peut modifier que les rôles faisant explicitement partie de son périmètre.

Les rôles administratifs, honorifiques ou appartenant à d'autres systèmes doivent rester intacts.

## Prévalidation avant mutation

L'executor effectue un preflight avant la première modification Discord.

## Secrets hors du dépôt

Les credentials et configurations locales sont fournis par variables d'environnement.

Les fichiers locaux `.env.*` et les bases SQLite runtime sont exclus du dépôt.

Seul :

```text
.env.example
```

est versionné afin de documenter la configuration attendue.

## Conteneur non-root

L'image Docker de production utilise un utilisateur dédié non privilégié.

---

# Reporting et observabilité

La V1.0 dispose déjà d'un système de reporting structuré capable de publier des événements vers plusieurs reporters.

Une défaillance d'un reporter ne doit pas empêcher les autres destinations de recevoir l'événement.

La V1.1 doit renforcer cette infrastructure autour de trois usages distincts :

```text
report-activity
→ actions fonctionnelles réussies

report-error
→ erreurs, incidents et comportements dégradés

admin-commands
→ point d'entrée dédié aux opérations administratives
```

Exemples futurs de rapports d'activité :

```text
Rôle attribué
Rôle retiré
Questionnaire appliqué
Message privé envoyé
Catalogue synchronisé
Snapshot de configuration mis à jour
```

Les commandes administratives resteront protégées par des contrôles d'autorisation applicatifs.

Le fait qu'une commande soit exécutée dans un salon administratif ne constituera jamais à lui seul une autorisation.

---

# Tests

Claviger dispose de plus de **250 tests automatisés** couvrant notamment :

- modèles métier ;
- politiques de serveur ;
- repositories SQLite ;
- migrations ;
- découverte Discord ;
- synchronisation des catalogues ;
- questionnaires ;
- planners ;
- executors ;
- coordinators ;
- autorisations ;
- reporting ;
- commandes Discord ;
- interfaces Discord ;
- composition globale du bot.

Les tests utilisent des environnements temporaires et des doubles de test afin de ne pas dépendre du serveur Discord de production.

En complément, les fonctionnalités nécessitant une validation Discord réelle sont testées dans un environnement d'intégration dédié.

---

# Environnement de développement

La production et le développement utilisent désormais deux environnements Discord différents.

```text
Production
├── Bot de production
├── Serveur de production
├── Base SQLite de production
└── Configuration de production

Development
├── Bot de développement
├── Serveur Discord de test
├── Base SQLite de développement
└── Configuration de développement
```

Cet environnement permet notamment de tester :

- un bootstrap sur un serveur neuf ;
- des conventions de noms différentes de la production ;
- les associations rôle ↔ salon ;
- les migrations ;
- les catalogues ;
- les erreurs de configuration ;
- les problèmes de hiérarchie Discord ;
- les nouveaux workflows avant déploiement.

La V1.1 doit également rendre la sélection de l'environnement explicite afin d'éviter qu'une instance de développement puisse démarrer accidentellement avec une configuration de production, ou inversement.

---

# V1.1 — Consolidation

La V1.1 n'a pas pour objectif d'ajouter une grande quantité de fonctionnalités.

Elle vise principalement à rendre la V1.0 plus fiable, observable et générique avant de continuer à enrichir le produit.

Le développement suit volontairement une approche incrémentale :

```text
Une modification cohérente
    ↓
Tests ciblés
    ↓
Suite complète
    ↓
Test Discord réel si nécessaire
    ↓
Commit
```

Aucune refonte globale n'est prévue sans justification fonctionnelle.

---

## Isolation Development / Production

La configuration doit évoluer vers des environnements explicitement séparés :

```text
.env.development
.env.production
.env.example
```

Les objectifs sont notamment :

- empêcher le chargement accidentel du mauvais environnement ;
- valider les variables obligatoires au démarrage ;
- détecter les incohérences de configuration ;
- sécuriser les futurs déploiements ;
- documenter clairement les différences DEV / PROD.

---

## Classification des accès adultes

La V1.0 a révélé un cas métier non couvert : tous les accès adultes ne sont pas nécessairement organisés en paires IA / non-IA.

La V1.1 doit donc introduire une classification partagée.

### Paire

```text
access-no-ia-test
access-ia-test
```

Les deux rôles représentent les variantes d'un même thème.

### Accès indépendant

```text
access-test
```

L'accès ne dépend pas de la préférence IA.

### IA uniquement

```text
access-ia-solo
```

Aucune variante `access-no-ia-solo` n'existe.

L'accès ne doit être proposé que lorsque l'utilisateur autorise les contenus IA.

### Entrée no-IA sans paire

```text
access-no-ia-single
```

Ce cas doit être détecté explicitement afin que le scanner et le workflow puissent signaler ou traiter correctement une paire incomplète.

La même logique de classification devra être utilisée par :

```text
Role scan
Questionnaire adulte
Planner
```

afin d'éviter plusieurs interprétations différentes de la même configuration Discord.

---

## Nouveau diagnostic des rôles

Le role scan doit devenir un véritable outil d'observation de la configuration.

L'objectif est de pouvoir afficher clairement :

```text
PAIRS
SOLO
IA ONLY
NO-IA ONLY / INCOMPLETE
UNMANAGEABLE
ANOMALIES
```

Il doit également permettre de détecter :

- les rôles hors de portée du bot ;
- les rôles Discord administrés automatiquement ;
- les mappings manquants ou ambigus ;
- les conventions de catalogue incohérentes.

Le scanner et les workflows devront s'appuyer sur les mêmes règles métier.

---

## Questionnaire adulte multi-étapes

Le questionnaire adulte doit évoluer vers un parcours adaptatif.

Conceptuellement :

```text
Commande adulte
    ↓
Analyse du catalogue
    ↓
Modal des accès IA / no-IA
    ↓
Accès complémentaires disponibles ?
    ├── Oui → seconde modal
    └── Non → validation
    ↓
Plan complet
    ↓
Execution
```

La seconde modal ne doit être ouverte que lorsqu'elle contient réellement quelque chose à proposer.

Les accès IA-only doivent également être filtrés en fonction de la préférence IA sélectionnée.

Aucune mutation Discord ne doit être effectuée entre les deux modals.

L'ensemble des choix doit être validé avant la génération du plan final.

---

## Autorisations Trusted / Moderator

La V1.0 utilise encore partiellement la hiérarchie Discord comme signal de confiance.

La V1.1 doit séparer deux concepts :

```text
Hiérarchie Discord
→ ce que Claviger peut techniquement manipuler

Policy Claviger
→ qui a le droit de demander une action
```

Deux rôles fonctionnels sont prévus dans la policy :

```text
trusted_role_id
moderator_role_id
```

Le rôle Trusted donnera accès aux commandes privilégiées non liées à la modération.

Le rôle Moderator donnera accès aux opérations de modération et pourra également bénéficier des droits Trusted.

Les rôles honorifiques ou visuels d'un serveur n'auront plus automatiquement de signification de sécurité.

---

## Last Known Good Snapshot

La base SQLite reste la source persistante principale de configuration.

La V1.1 prévoit cependant un mécanisme de dernier état valide par serveur :

```text
guild_id
    ↓
Last Known Good Snapshot
```

Le snapshot doit permettre à Claviger de conserver certaines fonctionnalités de lecture et d'accès lorsque SQLite devient temporairement indisponible.

Il doit contenir uniquement l'état fonctionnel nécessaire au mode dégradé :

- policy effective ;
- catalogues nécessaires ;
- rôles d'autorisation ;
- identifiants Discord ;
- métadonnées utiles ;
- version du format ;
- date de génération.

Les opérations modifiant la configuration persistante resteront bloquées lorsque la base principale est indisponible.

Discord restera l'autorité finale pour vérifier qu'un rôle existe encore et peut réellement être manipulé.

---

## Mutations Discord partielles

Les executors réalisent déjà un preflight complet avant la première mutation.

La V1.1 doit également améliorer le diagnostic lorsqu'un échec survient après le début de l'exécution.

Exemple :

```text
Ajout rôle A     OK
Retrait rôle B   OK
Ajout rôle C     FAILED
```

Claviger doit pouvoir indiquer précisément :

- les opérations déjà réussies ;
- l'opération ayant échoué ;
- le rôle concerné ;
- le contexte technique de l'erreur.

L'objectif n'est pas de prétendre que plusieurs appels Discord sont transactionnels, mais de rendre les états partiels explicitement observables.

---

## Logging et erreurs

La consolidation doit notamment apporter :

- configuration explicite du logging runtime ;
- suppression progressive des erreurs silencieuses ;
- conservation du traceback local ;
- reporting utilisateur distinct du diagnostic technique ;
- meilleure séparation entre INFO, WARNING et ERROR ;
- protection contre l'exposition inutile de détails internes dans Discord.

---

## Nommage interne

Certains noms internes de la V1.0 correspondent encore directement au thème du serveur d'origine.

Par exemple :

```text
Noctis...
```

La V1.1 doit progressivement préférer des concepts de domaine plus génériques :

```text
AdultAccess...
```

sans nécessairement modifier immédiatement les noms visibles des commandes Discord.

L'objectif est de distinguer :

```text
Présentation spécifique au serveur
≠
Concept métier interne
```

---

## Build et CI

La consolidation prévoit également :

- dépendances reproductibles ;
- exécution automatisée de Ruff ;
- exécution automatisée de pytest ;
- CI GitHub ;
- contrôles avant intégration sur la branche stable.

---

# V1.2 — Onboarding

La V1.2 introduira le parcours d'arrivée automatique d'un nouveau membre.

Exemple :

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

Cette évolution sera développée sur la base consolidée par la V1.1.

---

# V1.3 — Administration Web et modération

La V1.3 doit introduire une véritable interface d'administration.

L'objectif est de pouvoir sélectionner un serveur Discord et modifier sa configuration sans intervenir directement dans SQLite.

Exemples de fonctions prévues :

```text
Serveurs
├── sélectionner une guild
├── consulter son état
└── inspecter sa configuration

Policies
├── rôles fonctionnels
├── permissions
├── salons
└── options du serveur

Catalogues
├── labels
├── descriptions
├── emojis
├── ordre
└── activation

Modération
├── rôles Trusted / Moderator
├── commandes dédiées
└── journalisation
```

Cette étape doit également préparer une séparation plus nette entre :

```text
Configuration
Supervision
```

---

# Évolution IA

L'intégration d'une intelligence artificielle n'est pas le point de départ de Claviger.

Le projet cherche d'abord à fournir des outils métiers déterministes, testables et sécurisés.

À terme, une IA pourra utiliser certains de ces outils selon des permissions explicites.

Conceptuellement :

```text
Utilisateur
    ↓
Interface conversationnelle
    ↓
LLM / Agent
    ↓
Outils Claviger
    ↓
Services métier existants
    ↓
Discord / autres ressources
```

L'objectif est que l'IA ne contourne pas les règles métier.

Elle devra utiliser les mêmes services, contrôles et autorisations que les interfaces classiques.

Les évolutions envisagées comprennent notamment :

- réponses conversationnelles Discord ;
- mémoire contextualisée ;
- supervision Web des conversations ;
- outils contrôlés ;
- automatisations ;
- actions proactives limitées ;
- modèles locaux ou APIs interchangeables.

---

# Technologies

Le projet utilise actuellement principalement :

- **Python 3.12**
- **discord.py**
- **SQLite**
- **aiosqlite**
- **python-dotenv**
- **pytest**
- **pytest-asyncio**
- **Ruff**
- **Docker**

Le projet utilise une structure Python `src/` et expose un point d'entrée applicatif dédié.

---

# Déploiement

La production utilise une image basée sur :

```text
python:3.12-slim
```

Le conteneur :

- installe uniquement le package applicatif nécessaire ;
- utilise un utilisateur non-root dédié ;
- reçoit sa configuration depuis l'environnement ;
- conserve les données runtime hors de l'image.

Le développement et la production ne doivent jamais partager leurs credentials ou leur base de données.

---

# Branches

Le workflow actuel utilise principalement :

```text
main
→ version stable

develop
→ développement de la prochaine version

deployment branch
→ état utilisé pour le déploiement contrôlé
```

Les changements sont développés et testés avant d'être intégrés dans la branche stable.

La mise en place d'une CI et de protections supplémentaires de branche fait partie de la consolidation V1.1.

---

# Documentation technique

Le dépôt contient également une documentation complémentaire dans :

```text
documentations/
```

Elle comprend notamment :

- le cadrage initial du projet ;
- une rétrospective de développement ;
- des audits d'architecture ;
- une documentation technique ;
- un audit sécurité / logs / observabilité ;
- des documents de déploiement.

Ces documents servent également de base à la consolidation V1.1.

---

# Développement assisté par intelligence artificielle

Claviger est développé avec l'assistance d'une intelligence artificielle.

Cette utilisation est volontairement documentée.

L'IA intervient notamment pour :

- challenger les choix d'architecture ;
- proposer des implémentations ;
- identifier des cas limites ;
- analyser les erreurs ;
- proposer ou compléter des tests ;
- relire le code ;
- documenter les décisions ;
- préparer des audits.

Le projet n'est cependant pas développé de manière autonome par une IA.

Le workflow repose sur une boucle de validation humaine :

```text
Besoin réel
    ↓
Conception / discussion
    ↓
Proposition assistée
    ↓
Analyse humaine
    ↓
Implémentation
    ↓
Tests
    ↓
Test fonctionnel réel
    ↓
Validation
```

Les règles métier, les arbitrages d'architecture, la validation du comportement et les décisions finales restent sous responsabilité humaine.

L'utilisation de l'IA est considérée ici comme un outil d'ingénierie, pas comme un substitut à la compréhension du système.

---

# Principes de développement

Claviger suit actuellement quelques règles simples :

- éviter le code jetable ;
- privilégier les modules réutilisables lorsqu'une abstraction est réellement justifiée ;
- ne pas généraliser avant d'avoir plusieurs cas concrets ;
- séparer calcul métier et effets de bord ;
- tester chaque évolution ;
- conserver la compatibilité avec les comportements validés ;
- privilégier les IDs Discord aux noms pour l'identité persistante ;
- échouer explicitement plutôt que silencieusement ;
- conserver une séparation stricte entre développement et production ;
- améliorer progressivement le système plutôt que lancer des refactorisations globales.

---

# Pourquoi « Claviger » ?

Le nom provient de l'identité du serveur pour lequel le projet a été initialement développé.

Le projet conserve cette origine dans certains noms publics historiques.

Son architecture évolue cependant progressivement vers des concepts plus génériques afin que ses composants puissent être réutilisés dans d'autres contextes.

Claviger est ainsi à la fois un bot réellement utilisé et un projet d'expérimentation autour de l'architecture logicielle, de l'automatisation Discord et du développement assisté par intelligence artificielle.
