# Configuration des workflows — état V1.1

Ce document décrit le jalon atteint par la configuration générique des workflows
dans Claviger V1.1.

Il complète le `README.md` sans le remplacer. Le README principal devra être
actualisé après le smoke test Discord réel, afin de documenter un comportement
effectivement validé sur serveur et pas seulement couvert par les tests.

---

## Objectif du jalon

Le parcours de configuration d'un serveur doit pouvoir partir d'une guild sans
structure Claviger et aboutir à une configuration persistée sans logique métier
cachée dans l'interface Discord.

Le flux actuellement implémenté est :

```text
/{bot} config-server
        ↓
contrôles DB / ownership
        ↓
configuration ADMIN
        ↓
ADMIN persistée et exploitable ?
        ├── non → poursuite interactive ADMIN uniquement
        └── oui
              ↓
        configuration Workflow
              ↓
        métadonnées
        + ressources existing/create
        + option IA
              ↓
        résumé explicite
              ↓
        confirmation humaine
              ↓
        validation
              ↓
        discovery fraîche
              ↓
        reconciliation
              ↓
        preflight Discord
              ↓
        provisioning
              ↓
        persistence SQLite
              ↓
        proposition de restart
```

---

## Contrat frontend-neutral

L'interface Discord ne persiste pas directement les choix et ne crée pas
elle-même les ressources.

Elle construit un :

```text
WorkflowConfigurationDraft
```

Ce contrat représente notamment :

- l'identité fonctionnelle du workflow ;
- le nom et la description de commande ;
- la catégorie ;
- le salon de gestion ;
- le salon d'exécution ;
- le rôle principal ;
- le préfixe du questionnaire ;
- l'activation éventuelle du contexte IA ;
- le rôle de préférence IA lorsqu'il doit être créé ou sélectionné.

Les choix de ressources sont exprimés en mode :

```text
existing
ou
create
```

Le même contrat pourra être produit plus tard par l'interface Web sans
réimplémenter la logique de configuration.

---

## Discovery

`WorkflowStructureDiscoveryService` observe Discord sans mutation.

Il expose :

- les catégories disponibles ;
- les salons texte disponibles ;
- leurs permissions effectives ;
- les rôles que Claviger peut réellement gérer ;
- la capacité actuelle à créer/réparer des salons ;
- la capacité actuelle à créer des rôles.

La hiérarchie des rôles reste centralisée dans `RoleDiscoveryService`.

---

## Reconciliation

La réconciliation confronte un draft validé au snapshot Discord courant.

Elle refuse notamment :

- une ressource existante disparue ;
- un rôle devenu non gérable ;
- un salon existant situé hors de la catégorie sélectionnée ;
- la tentative de rattacher silencieusement un salon existant à une catégorie
  qui doit encore être créée ;
- une création impossible faute de permissions ;
- une collision entre rôle principal et rôle de préférence IA ;
- le remplacement silencieux du rôle IA partagé par la guild.

Les incohérences sont rejetées avant provisioning.

---

## Provisioning

`WorkflowStructureProvisioningService` refait un preflight juste avant la
première mutation Discord.

Il peut ensuite :

- créer la catégorie ;
- créer le salon de gestion ;
- créer le salon d'exécution ;
- créer le rôle principal ;
- créer le rôle de préférence IA ;
- réutiliser des ressources existantes ;
- réparer uniquement les permissions nécessaires au fonctionnement du workflow.

Le salon de gestion interdit l'écriture ordinaire à `@everyone` tout en
garantissant l'accès du bot. Les administrateurs Discord conservent leurs
capacités natives.

Le salon d'exécution conserve les permissions membres héritées de sa catégorie
et garantit seulement l'accès nécessaire à Claviger.

---

## Persistence SQLite

Le schéma V10 complète l'identité structurelle d'un workflow avec :

```text
category_id
management_channel_id
primary_role_id
```

Les salons d'exécution restent dans la table de binding dédiée, car un workflow
peut en posséder plusieurs.

La persistence enregistre de manière atomique :

- la définition du workflow ;
- son catalogue questionnaire principal ;
- le binding du salon d'exécution ;
- le contexte IA lorsque nécessaire.

La préférence IA utilise le modèle de contexte générique existant. Elle n'ajoute
pas un second booléen métier parallèle dans `guild_workflows`.

---

## Interface Discord

Le wizard Discord :

1. collecte les métadonnées dans une modal ;
2. propose pour chaque ressource `utiliser l'existant` ou `créer` ;
3. utilise les sélecteurs natifs Discord pour catégories, salons et rôles ;
4. propose l'activation de l'IA ;
5. réutilise automatiquement le rôle IA déjà partagé par la guild ;
6. affiche un résumé complet ;
7. ne déclenche aucune mutation avant confirmation explicite ;
8. remet ensuite le draft au coordinator backend.

Cette séparation est volontaire :

```text
Discord UI
    ↓
WorkflowConfigurationDraft
    ↓
WorkflowConfigurationCoordinatorService
    ↓
services métier / Discord / SQLite
```

---

## Intégration avec ADMIN

La configuration Workflow ne démarre que si ADMIN est réellement persistée et
complète.

`run_admin_configuration()` renvoie désormais l'état de readiness à son
orchestrateur.

Les chemins ambigus ou incomplets (`IMPORT`, `NEEDS_CHOICE`, routing explicite)
restent fail-closed et terminent d'abord leur parcours ADMIN.

Sur une guild vierge, le chemin nominal devient donc :

```text
config-server
→ CREATE ADMIN
→ ADMIN READY
→ wizard Workflow
```

Ce chemin est celui visé par le smoke test du jalon.

---

## Frontière actuelle du runtime

La configuration générique est désormais fonctionnelle de bout en bout pour la
création, la réconciliation, le provisioning et la persistence.

En revanche, **l'exécution générique des workflows persistés n'est pas encore le
même problème**.

Le runtime actuel possède encore deux façades historiques explicites :

```text
/membre
/noctis
```

Elles utilisent leurs services, catalogues et modals historiques.

Il serait incorrect de faire apparaître arbitrairement `command_name` depuis
SQLite puis de deviner quel moteur historique doit l'exécuter. Le modèle
persistant ne possède pas encore de contrat explicite reliant une définition
générique à un handler runtime.

La suite V1.1 devra donc introduire cette liaison explicitement avant de rendre
la surface d'exécution entièrement pilotée par les définitions persistées.

Aucune heuristique basée sur :

- le nom de commande ;
- le préfixe de rôle ;
- le nom du workflow ;
- le nom des salons ;

ne doit servir à choisir silencieusement un moteur d'exécution.

---

## Smoke test attendu

Sur la guild DEV vierge :

1. déployer le commit contenant cette architecture ;
2. migrer la base jusqu'au schéma courant ;
3. vérifier l'ownership applicatif ;
4. lancer `/{bot} config-server` ;
5. laisser Claviger créer ADMIN ;
6. entrer dans le wizard Workflow sans restart intermédiaire ;
7. créer une catégorie Workflow ;
8. créer un salon de gestion ;
9. créer un salon d'exécution ;
10. créer un rôle principal ;
11. tester IA désactivée puis, lors d'un second essai si utile, IA activée ;
12. vérifier le résumé avant confirmation ;
13. confirmer ;
14. vérifier les ressources créées sur Discord ;
15. vérifier les permissions du salon de gestion ;
16. vérifier que la persistence réussit ;
17. effectuer le restart proposé.

Le smoke valide la **configuration générique**. Il ne doit pas être présenté
comme la validation d'un moteur d'exécution générique qui n'existe pas encore.

---

## Critère de fermeture de ce jalon

Le jalon est validé lorsque le serveur DEV vierge peut être configuré depuis
`config-server` jusqu'à la persistence du premier workflow, sans modification
manuelle de SQLite et sans création manuelle préalable des ressources Discord.

Après validation réelle, le README principal peut être mis à jour avec ce
comportement comme fonctionnalité V1.1 effectivement vérifiée.
