# Claviger V1.1 — Arborescence cible de fin de version

## Statut

Document de préparation.

Cette structure est **la cible de réorganisation**, pas encore l'état actuel du code.

Le ZIP qui contient ce document prépare les dossiers avec leurs README, mais ne déplace aucun fichier Python et ne modifie aucun test existant.

---

## Pourquoi réorganiser

Plusieurs dossiers ont grandi suffisamment pour que leur lecture devienne coûteuse.

Le cas principal est `services/`, qui regroupe actuellement dans un seul niveau :

- ADMIN ;
- catalogues ;
- contexte ;
- rôles ;
- runtime ;
- workflows ;
- services transversaux.

La réorganisation vise à rendre les responsabilités visibles dans le système de fichiers sans modifier le comportement du produit.

La même logique s'applique aux `models`, `repositories`, `commands`, `ui` et tests.

---

## Cible générale

```text
src/
└── claviger/
    ├── commands/
    │   ├── admin/
    │   ├── general/
    │   └── workflows/
    ├── constants/
    ├── database/
    ├── models/
    │   ├── admin/
    │   ├── catalogs/
    │   ├── context/
    │   ├── roles/
    │   ├── runtime/
    │   └── workflows/
    ├── policies/
    ├── reporting/
    ├── repositories/
    │   ├── admin/
    │   ├── catalogs/
    │   ├── context/
    │   ├── runtime/
    │   └── workflows/
    ├── services/
    │   ├── admin/
    │   ├── catalogs/
    │   ├── context/
    │   ├── roles/
    │   ├── runtime/
    │   └── workflows/
    └── ui/
        ├── admin/
        ├── catalogs/
        └── workflows/
```

Les fichiers globaux comme `bot.py`, `main.py` et `config.py` restent à la racine du package tant qu'une extraction apporte moins de valeur que leur rôle actuel de bootstrap / composition.

Les services véritablement simples et transversaux peuvent également rester directement dans `services/` si créer un sous-dossier pour un seul fichier n'apporte rien.

---

# Répartition proposée

## Commands

### `commands/admin/`

Candidats actuels :

- `admin_command_group.py`
- `catalog_command.py`
- `claviger_command.py`
- `config_server_command.py`
- `database_command.py`
- `guild.py`
- `report.py`
- `restart_command.py`
- `roles.py`

### `commands/workflows/`

- `member_command.py`
- `noctis_command.py`

### `commands/general/`

- `say_command.py`

Cette répartition est fonctionnelle : administration, workflows utilisateur et commande générale simple.

---

## Services

### `services/admin/`

- `admin_configuration_coordinator_service.py`
- `admin_configuration_reconciliation_service.py`
- `admin_structure_discovery_service.py`
- `admin_structure_provisioning_service.py`

### `services/catalogs/`

- `catalog_next_coordinator_service.py`
- `catalog_registry_service.py`
- `catalog_sync_coordinator_service.py`
- `catalog_sync_planner_service.py`
- `catalog_variant_classifier.py`
- `role_channel_discovery_service.py`

### `services/context/`

- `context_capability_registry_service.py`
- `context_resolver_service.py`
- `questionnaire_context_planner_service.py`
- `workflow_context_validator_service.py`

### `services/roles/`

- `role_classifier.py`
- `role_discovery.py`
- `role_manageability_service.py`
- `role_manager_service.py`

### `services/runtime/`

- `authorization.py`
- `database_ownership_service.py`
- `discord_identity_service.py`
- `guild_configuration_readiness_service.py`
- `guild_policy_bootstrap.py`

### `services/workflows/`

- `adult_access_classifier.py`
- `adult_access_questionnaire_service.py`
- `adult_access_workflow_service.py`
- `member_interest_questionnaire_service.py`
- `member_role_executor_service.py`
- `member_role_planner_service.py`
- `member_workflow_coordinator_service.py`
- `noctis_role_executor_service.py`
- `noctis_role_planner_service.py`
- `noctis_workflow_coordinator_service.py`
- `workflow_configuration_coordinator_service.py`
- `workflow_configuration_reconciliation_service.py`
- `workflow_configuration_validation_service.py`
- `workflow_structure_discovery_service.py`
- `workflow_structure_provisioning_service.py`

### Racine `services/`

`SayService` peut rester temporairement à la racine tant qu'il est le seul service de son petit domaine.

Il ne faut pas créer un dossier `say/` uniquement pour obtenir une arborescence parfaitement symétrique.

---

## Models

### `models/admin/`

- modèles `admin_*`
- `guild_admin_configuration_model.py`

### `models/catalogs/`

- `adult_access.py`
- `member_interest.py`
- modèles `catalog_*`
- `role_channel_catalog_model.py`
- `role_channel_discovery_model.py`

### `models/context/`

- `context_capability_model.py`
- `context_definition_model.py`
- `questionnaire_context_question_model.py`
- `resolved_context_model.py`

### `models/roles/`

- `member_role_execution_result_model.py`
- `member_role_plan_model.py`
- `noctis_role_execution_result_model.py`
- `noctis_role_plan_model.py`

### `models/runtime/`

- `discord_application_identity_model.py`
- `discord_guild_identity_model.py`
- `discord_runtime_identity_model.py` tant que la compatibilité existe
- `guild_configuration_readiness_model.py`
- `guild_runtime_state_model.py`
- `runtime_restart_model.py`

### `models/workflows/`

- `adult_access_classification_model.py`
- `adult_access_questionnaire_model.py`
- `adult_access_theme_model.py`
- `member_interest_questionnaire_model.py`
- `resolved_workflow_configuration_model.py`
- modèles `workflow_*`

---

## Repositories

### `repositories/admin/`

- `guild_admin_configuration_repository.py`

### `repositories/catalogs/`

- `access_catalog_repository.py`
- `catalog_definition_repository.py`
- `interest_catalog_repository.py`
- `role_channel_catalog_repository.py`

### `repositories/context/`

- `context_definition_repository.py`

### `repositories/runtime/`

- `database_ownership_repository.py`
- `guild_policy_repository.py`

### `repositories/workflows/`

- `workflow_configuration_repository.py`
- `workflow_definition_repository.py`

---

## UI

### `ui/admin/`

- `admin_configuration_view.py`

### `ui/catalogs/`

- `catalog_metadata_modal.py`
- `catalog_next_view.py`
- `catalog_selection_modal.py`

### `ui/workflows/`

- `member_questionnaire_modal.py`
- `noctis_questionnaire_modal.py`
- `workflow_configuration_session.py`
- `workflow_configuration_view.py`

---

# Tests : réorganisation nécessaire

**Oui.**

La suite de tests est déjà mieux structurée que certains dossiers de `src`, mais elle ne reflète pas encore complètement la cible.

État observé :

- `tests/services/` possède déjà `admin/`, `catalogs/`, `context/`, `roles/`, `workflows/` ;
- plusieurs tests de services restent encore directement dans `tests/services/` ;
- `tests/commands/` possède déjà `admin/`, mais les tests de workflows et de `say` restent à la racine ;
- `tests/repository/` est au singulier alors que le code utilise `repositories/` ;
- `tests/test_policies/` ne suit pas le nom de `src/claviger/policies/` ;
- `tests/models/` devra suivre les nouveaux sous-domaines ;
- `tests/ui/` devra suivre les nouveaux sous-domaines.

La cible est donc :

```text
tests/
├── commands/
│   ├── admin/
│   ├── general/
│   └── workflows/
├── database/
├── models/
│   ├── admin/
│   ├── catalogs/
│   ├── context/
│   ├── roles/
│   ├── runtime/
│   └── workflows/
├── policies/
├── reporting/
├── repositories/
│   ├── admin/
│   ├── catalogs/
│   ├── context/
│   ├── runtime/
│   └── workflows/
├── runtime/
├── services/
│   ├── admin/
│   ├── catalogs/
│   ├── context/
│   ├── roles/
│   ├── runtime/
│   └── workflows/
└── ui/
    ├── admin/
    ├── catalogs/
    └── workflows/
```

`tests/runtime/` reste une exception volontaire : il teste le cycle de vie et l'application assemblée autour de `ClavigerBot`, pas un seul module.

---

# Stratégie de migration

Ne pas déplacer tous les fichiers d'un coup.

Ordre recommandé :

1. `commands/`
2. `models/`
3. `repositories/`
4. `services/`
5. `ui/`
6. normalisation finale de `tests/`
7. imports résiduels et exports `__init__.py`
8. suite complète
9. documentation principale
10. smoke test DEV

Pour chaque domaine :

```text
déplacer un groupe cohérent
→ corriger les imports
→ déplacer les tests correspondants
→ tests ciblés
→ Ruff
→ suite complète
→ commit
```

La réorganisation ne doit pas être combinée avec une évolution fonctionnelle majeure.

L'objectif de chaque commit est :

> mêmes comportements, meilleure navigation.
