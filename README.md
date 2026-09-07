# Claviger

Claviger est un bot Discord développé en Python pour automatiser l'attribution et la gestion de rôles à partir de questionnaires utilisateur.

La première version du projet répond à un besoin concret : permettre aux membres d'un serveur Discord de choisir eux-mêmes les espaces auxquels ils souhaitent accéder, tout en conservant une logique de permissions contrôlée, explicite et maintenable.

Claviger a été pensé dès le départ comme un projet modulaire pouvant évoluer au-delà de cette première fonction.

---

## Objectif de la V1

La V1 repose sur deux parcours distincts d'attribution de rôles.

### 1. Gestion des centres d'intérêt des membres

Un membre peut utiliser la commande :

`/membre`

Un questionnaire lui présente les différents centres d'intérêt disponibles sur le serveur.

Chaque choix correspond à un rôle Discord géré par Claviger.

Par exemple :

- musique ;
- jeux ;
- cuisine ;
- lecture ;
- création ;
- animaux ;
- autres catégories configurées par le serveur.

Lors de la validation du questionnaire, Claviger :

1. attribue le rôle de membre si nécessaire ;
2. ajoute les rôles correspondant aux intérêts sélectionnés ;
3. retire les intérêts précédemment sélectionnés qui ont été décochés ;
4. laisse totalement intacts les rôles qui ne sont pas sous sa responsabilité.

Le questionnaire peut être relancé à tout moment afin de modifier ses choix.

Les sélections actuelles sont restaurées automatiquement à partir des rôles réellement présents sur le membre.

---

## Accès membre et parcours d'arrivée

Sur le serveur pour lequel Claviger a été initialement développé, le parcours est volontairement séparé en deux étapes.

Le nouvel utilisateur commence par consulter le salon d'accueil et d'information.

Il doit ensuite se rendre dans le salon prévu pour l'intégration des nouveaux membres afin d'utiliser `/membre`.

L'objectif n'est pas seulement technique : ce parcours demande à l'utilisateur de consulter les informations du serveur avant de procéder lui-même à son inscription dans les différentes catégories communautaires.

---

## 2. Gestion des accès 18+

Le second système ajoute une couche supplémentaire au mécanisme précédent.

Un utilisateur peut demander l'accès à une partie du serveur réservée aux adultes via :

`/noctis`

Ce parcours ajoute d'abord une distinction entre :

- un membre classique ;
- un membre disposant de l'accès 18+.

Une fois cet accès demandé, Claviger présente un questionnaire permettant de sélectionner différentes catégories de contenu adulte.

Cette partie du projet ajoute également une seconde dimension : la préférence concernant les contenus générés par intelligence artificielle.

---

## Contenu classique et contenu généré par IA

Pour une même catégorie, le serveur peut proposer deux variantes de rôle.

Exemple conceptuel :

```text
access-no-ia-theme
access-ia-theme
```

La première correspond au contenu classique de la catégorie, sans contenu généré par IA.

La seconde permet d'accéder également à sa variante contenant des créations générées par intelligence artificielle.

Le questionnaire demande donc :

1. les catégories auxquelles l'utilisateur souhaite accéder ;
2. s'il souhaite également voir les contenus générés par IA.

À partir de ces réponses, Claviger calcule les rôles devant être attribués.

Par exemple :

```text
Catégorie A sélectionnée
Catégorie B sélectionnée
Contenu IA désactivé

→ accès classique A
→ accès classique B
```

Avec l'option IA activée :

```text
Catégorie A sélectionnée
Catégorie B sélectionnée
Contenu IA activé

→ accès classique A
→ accès IA A
→ accès classique B
→ accès IA B
→ rôle global indiquant la préférence IA
```

La préférence IA est donc additive.

Activer les contenus IA ne remplace pas les accès classiques : cela ajoute les variantes correspondantes lorsqu'elles existent.

Cette distinction permet au serveur de proposer simultanément les deux types de contenu sans imposer l'un ou l'autre à ses membres.

---

## Une logique de réconciliation plutôt qu'une simple attribution

Claviger ne se contente pas d'ajouter un rôle à chaque clic.

Chaque soumission suit une logique de réconciliation :

```text
État actuel du membre
        +
Réponses au questionnaire
        +
Configuration du serveur
        ↓
État désiré
        ↓
Plan de modifications
        ↓
Vérification des permissions
        ↓
Ajout / retrait des rôles nécessaires
```

Le bot calcule donc les différences entre l'état actuel et l'état souhaité.

Cette approche permet notamment :

- de relancer un questionnaire sans produire de doublons ;
- de retirer proprement une ancienne sélection ;
- de conserver les rôles qui ne sont pas gérés par le questionnaire ;
- de vérifier les opérations avant la première modification Discord ;
- de rendre les opérations reproductibles et prévisibles.

---

## Sécurité des rôles

Claviger applique plusieurs précautions avant de modifier les rôles d'un utilisateur.

Avant toute opération, il vérifie notamment que :

- le rôle existe toujours sur Discord ;
- le rôle peut être géré par le bot ;
- le rôle n'est pas un rôle Discord administré automatiquement ;
- le rôle se trouve sous le rôle principal de Claviger dans la hiérarchie ;
- toutes les modifications prévues sont valides avant de commencer les changements.

Le bot ne considère pas tous les rôles Discord comme faisant partie de son domaine.

Chaque workflow ne manipule que les rôles qu'il connaît explicitement.

Un rôle administratif, de modération ou appartenant à un autre système reste donc hors de son périmètre.

---

## Catalogue et configuration

Les rôles proposés dans les questionnaires sont enregistrés dans une base SQLite.

Claviger distingue :

- l'état réellement découvert sur Discord ;
- les données techniques ;
- les métadonnées destinées aux utilisateurs.

Un élément du catalogue peut notamment contenir :

- l'identifiant Discord du rôle ;
- son nom ;
- une clé métier stable ;
- le salon associé ;
- un libellé ;
- une description ;
- un emoji ;
- son ordre d'affichage ;
- son état d'activation ;
- différents indicateurs permettant de vérifier que la configuration Discord reste cohérente.

Les noms Discord ne sont donc pas utilisés comme unique source d'identité.

---

## Architecture

Le projet est volontairement séparé en plusieurs couches.

```text
Discord
   ↓
Commands / UI
   ↓
Workflow Coordinators
   ↓
Questionnaire / Planner / Executor Services
   ↓
Repositories
   ↓
SQLite
```

### Questionnaire

Détermine les choix actuellement disponibles et ceux déjà sélectionnés par l'utilisateur.

### Planner

Compare l'état actuel et la sélection demandée pour construire un plan de modifications.

Il ne modifie pas Discord.

### Executor

Valide les opérations puis applique les ajouts et retraits de rôles.

### Coordinator

Orchestre le workflow complet sans placer toute la logique métier directement dans les commandes Discord.

### Repository

Gère la persistance sans décider de la logique métier.

Cette séparation rend les différentes parties plus faciles à tester, remplacer et réutiliser.

---

## Technologies

La V1 utilise principalement :

- Python 3.12 ;
- discord.py ;
- SQLite ;
- aiosqlite ;
- pytest ;
- Ruff.

Le projet contient une suite de tests couvrant notamment :

- les règles métier ;
- la construction des questionnaires ;
- la planification des modifications ;
- la sécurité de l'exécution ;
- les repositories ;
- la configuration des serveurs ;
- les commandes Discord ;
- les interfaces de questionnaire ;
- la composition globale du bot.

Au moment de la validation de la V1, la suite compte **252 tests automatisés**.

Des tests fonctionnels sont également réalisés directement sur Discord avant déploiement.

---

## Développement assisté par intelligence artificielle

Claviger a été développé avec l'assistance d'une intelligence artificielle.

L'IA est utilisée comme outil de développement, notamment pour :

- proposer des implémentations ;
- discuter et challenger des choix d'architecture ;
- identifier des cas limites ;
- proposer et compléter des tests ;
- analyser des erreurs ;
- suggérer des refactorisations ;
- documenter les décisions techniques.

Le développement ne repose cependant pas sur une génération autonome du projet.

Les besoins fonctionnels, les règles métier, les orientations d'architecture et les décisions finales sont définis, orientés et validés humainement.

Le processus de développement ressemble généralement à ceci :

```text
Besoin et orientation humains
        ↓
Discussion et propositions assistées par IA
        ↓
Analyse et arbitrage humains
        ↓
Implémentation
        ↓
Tests automatisés
        ↓
Correction / itération
        ↓
Validation humaine
        ↓
Test fonctionnel réel
```

L'assistance IA est volontairement documentée.

L'objectif n'est pas de masquer son utilisation, mais de montrer comment elle peut être intégrée dans un workflow de développement tout en conservant la compréhension du système, les décisions d'architecture, le contrôle du code et la validation finale du côté humain.

Claviger est donc autant un projet Discord qu'une expérimentation concrète autour du développement logiciel assisté par IA.

---

## État de la V1

La V1 couvre actuellement :

- attribution du rôle membre ;
- sélection et modification des centres d'intérêt ;
- restauration des choix existants ;
- accès réservé aux adultes ;
- sélection de catégories adultes ;
- préférence globale pour les contenus IA ;
- résolution des variantes IA / non-IA ;
- synchronisation des catalogues Discord ;
- configuration par serveur ;
- contrôles de permissions ;
- reporting administratif ;
- commandes d'administration ;
- tests automatisés ;
- validation fonctionnelle des principaux workflows sur Discord.

---

## Roadmap

### V1.0 — Gestion des rôles

Premier déploiement opérationnel du système de rôles.

La V1 constitue le socle fonctionnel de Claviger : les utilisateurs peuvent gérer leurs centres d'intérêt et leurs accès adultes via les questionnaires Discord.

### V1.1 — Onboarding

Ajout du parcours automatique lors de l'arrivée d'un utilisateur.

```text
Nouvel utilisateur
       ↓
Message privé de bienvenue
       ↓
Invitation à consulter le salon d'accueil
```

Si le message privé ne peut pas être envoyé :

```text
Échec du MP
    ↓
Mention publique neutre dans le salon d'accueil des nouveaux membres
    ↓
Journalisation de l'échec
```

Cette fonctionnalité est volontairement prévue après le premier déploiement afin de conserver une V1 initiale clairement délimitée et validée.

### Évolutions futures

Claviger a été conçu pour pouvoir évoluer vers d'autres domaines :

- administration multi-serveurs ;
- configuration dynamique des commandes ;
- interface Web d'administration ;
- outils de modération ;
- automatisations supplémentaires ;
- intégration de modèles de langage ;
- outils accessibles à une IA selon un système de permissions ;
- agent conversationnel Discord.

La gestion des rôles constitue donc le premier cas d'usage d'une architecture destinée à devenir plus générale.

---

## Pourquoi « Claviger » ?

Le nom s'inscrit dans l'identité du serveur pour lequel le projet a été initialement développé.

Son architecture vise cependant à séparer progressivement les concepts propres à ce serveur de la logique générique afin que ses différents modules puissent être réutilisés ailleurs.
