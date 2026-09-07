# Documentation de Claviger

Ce dossier regroupe les documents ayant accompagné la conception, le développement, l'analyse et la préparation au déploiement de Claviger.

Ils ne constituent pas uniquement une documentation produite après l'écriture du code.

L'objectif est également de conserver une trace du processus de développement : cadrage initial, développement assisté par intelligence artificielle, décisions humaines, validation fonctionnelle et audit critique avant mise en production.

---

## Organisation

```text
Documentations/
│
├── README.md
│
├── 00_Prompt_maitre_initial_Claviger.pdf
├── 01_Claviger_Retrospective_Interventions_Humaines_V1.pdf
│
└── audit_01/
    ├── 00_Prompt_maitre_audit_projet.pdf
    ├── 01_audit_architecture.pdf
    ├── 02_documentation_technique.pdf
    ├── 03_securite_logs_observabilite.pdf
    └── 04_guide_pedagogique_code.pdf
```

---

# 1. Cadrage initial

## `00_Prompt_maitre_initial_Claviger.pdf`

Prompt maître ayant servi de point de départ au projet.

Il ne demande pas simplement la création d'un bot Discord.

Il définit notamment :

- le contexte du serveur ;
- les différents niveaux d'accès ;
- la gestion des centres d'intérêt ;
- les contraintes liées aux rôles et permissions ;
- le parcours des nouveaux membres ;
- les problématiques liées aux espaces réservés aux adultes ;
- les possibilités d'automatisation ;
- les contraintes de sécurité ;
- la possibilité de développer des outils personnalisés ;
- une méthode de travail progressive avec validation humaine entre les étapes.

Ce document permet de comprendre le besoin à l'origine de Claviger avant l'écriture de son architecture actuelle.

---

# 2. Développement assisté par IA et décisions humaines

## `01_Claviger_Retrospective_Interventions_Humaines_V1.pdf`

Claviger a été développé avec une assistance importante de l'intelligence artificielle.

Ce document ne cherche pas à masquer cette assistance ni à attribuer artificiellement chaque ligne de code à une origine humaine.

Il analyse au contraire les interventions du développeur ayant réellement modifié la direction du projet pendant sa réalisation.

Il présente notamment les décisions concernant :

- le refus d'une architecture jetable ;
- la modularité ;
- la séparation entre Discord et la logique métier ;
- les mécanismes de synchronisation ;
- les règles de sécurité autour des rôles ;
- les identités techniques stables ;
- l'organisation des catalogues ;
- la distinction entre intérêt pour l'IA et préférence d'affichage de contenu IA ;
- la relation entre variantes IA et non-IA ;
- la préparation au multi-serveurs ;
- le périmètre des différentes versions ;
- les validations effectuées directement sur Discord.

L'objectif est de documenter le rôle humain dans un workflow de développement assisté par IA : définition du besoin, arbitrage, critique, correction et validation.

---

# 3. Audit pré-déploiement

Le dossier `audit_01/` correspond au premier audit complet du projet réalisé une fois la V1 fonctionnelle et testée.

L'objectif de cet audit n'était pas de justifier les choix déjà réalisés.

Le prompt demandé à l'auditeur d'adopter une posture volontairement critique et de signaler les défauts d'architecture, de sécurité, de journalisation ou de maintenabilité réellement observables dans le code.

Cet audit sert donc à la fois :

- d'état des lieux de la V1 ;
- de contrôle avant le premier déploiement ;
- de documentation technique ;
- de source pour le backlog des versions suivantes.

---

## `audit_01/00_Prompt_maitre_audit_projet.pdf`

Prompt maître utilisé pour réaliser l'audit.

Il définit les critères d'analyse et impose notamment :

- une critique factuelle et argumentée ;
- l'analyse de l'architecture réelle ;
- l'étude de la séparation des responsabilités ;
- l'analyse de la dette technique ;
- l'évaluation de la sécurité ;
- l'étude des logs et de l'observabilité ;
- l'analyse de la stratégie de tests ;
- la préparation à la production ;
- la préparation aux futurs composants IA ;
- un classement des recommandations par priorité.

Conserver le prompt permet de comprendre sous quelles contraintes les documents suivants ont été produits.

---

## `audit_01/01_audit_architecture.pdf`

Audit technique et architectural de la V1.

Il analyse notamment :

- la structure générale du projet ;
- les responsabilités des différentes couches ;
- les principaux workflows ;
- la persistance SQLite ;
- les mécanismes de synchronisation ;
- la gestion des rôles Discord ;
- les policies ;
- la testabilité ;
- la préparation au multi-serveurs et à de futures interfaces IA ;
- les forces réellement observées ;
- les problèmes architecturaux ;
- la dette technique ;
- les refactorings recommandés.

Les recommandations sont classées par priorité afin de distinguer ce qui doit être traité rapidement de ce qui peut rester une dette acceptable pour une première version.

---

## `audit_01/02_documentation_technique.pdf`

Documentation technique de l'état du projet au moment de l'audit.

Elle décrit le fonctionnement réel de Claviger :

- arborescence et responsabilités ;
- modèles ;
- services ;
- repositories ;
- policies ;
- système de reporting ;
- fonctionnement de `/membre` ;
- fonctionnement de `/noctis` ;
- synchronisation des catalogues ;
- base SQLite ;
- planification puis exécution des mutations de rôles.

Ce document sert principalement de référence technique pour comprendre le code sans devoir commencer par parcourir l'ensemble du dépôt.

---

## `audit_01/03_securite_logs_observabilite.pdf`

Analyse dédiée à la sécurité opérationnelle, aux erreurs, aux logs et à l'observabilité.

Elle identifie notamment les limites concernant :

- les erreurs insuffisamment journalisées ;
- la conservation des tracebacks ;
- la configuration du logging ;
- les mutations Discord pouvant être partiellement appliquées ;
- la cohérence des règles de gestion des rôles ;
- l'identification des ressources Discord ;
- l'intégrité des catalogues ;
- les comportements en cas d'indisponibilité de la base ;
- la reproductibilité du déploiement ;
- le reporting.

Ce document constitue une source importante du backlog de fiabilisation suivant le premier déploiement.

---

## `audit_01/04_guide_pedagogique_code.pdf`

Guide complémentaire destiné à expliquer le code et les choix techniques de manière pédagogique.

Il ne se limite pas à décrire les classes.

Il cherche à expliquer pourquoi certaines décisions ont été prises, par exemple :

- pourquoi séparer questionnaire, planner, executor et coordinator ;
- pourquoi reconstruire l'état réel avant une mutation ;
- pourquoi effectuer un preflight avant de modifier Discord ;
- pourquoi utiliser des modèles immuables ;
- pourquoi certaines données utilisent des tuples plutôt que des listes ;
- pourquoi SQLite est suffisant pour cette première version ;
- comment fonctionnent les transactions ;
- comment les tests servent de documentation exécutable ;
- comment diagnostiquer les principaux workflows.

Ce document permet également de conserver une compréhension du projet indépendamment de l'assistance IA utilisée pendant son développement.

---

# 4. Chronologie documentaire

La documentation peut être lue comme une chronologie du projet :

```text
Cadrage initial
       ↓
Prompt maître Claviger

Conception et développement
       ↓
Assistance IA + arbitrages humains
       ↓
252 tests automatisés
       ↓
Validation fonctionnelle sur Discord

Analyse avant déploiement
       ↓
Prompt maître d'audit
       ↓
Audit architectural
       ↓
Documentation technique
       ↓
Analyse sécurité / logs / observabilité
       ↓
Guide pédagogique du code

Premier déploiement
       ↓
Retours d'exploitation

Versions suivantes
       ↓
Corrections et évolutions guidées
par l'audit et l'expérience réelle
```

---

# 5. Pourquoi conserver ces documents dans le dépôt ?

Le code permet de voir **ce que fait Claviger**.

Cette documentation permet également de comprendre :

- pourquoi le projet existe ;
- comment son architecture a été construite ;
- comment l'assistance IA a été utilisée ;
- quelles décisions sont restées sous contrôle humain ;
- quels compromis ont été volontairement acceptés pour la V1 ;
- quels problèmes sont déjà connus ;
- quelles évolutions sont prévues ;
- comment le projet est passé d'une idée à une application destinée à être réellement déployée.

Le dossier ne cherche donc pas à présenter une V1 comme un système terminé ou parfait.

Il documente au contraire son cycle de développement et d'amélioration continue.

---

## État documentaire

Les documents du dossier `audit_01/` correspondent à un instant donné du projet.

Ils ne doivent pas nécessairement être modifiés après chaque évolution du code.

Lorsqu'un nouvel audit important sera réalisé, il pourra être conservé séparément afin de rendre visible l'évolution du projet dans le temps.

Par exemple :

```text
Documentations/
├── audit_01/
├── audit_02/
└── ...
```

Cela permet de conserver à la fois l'historique des constats et la manière dont la dette technique a progressivement été traitée.