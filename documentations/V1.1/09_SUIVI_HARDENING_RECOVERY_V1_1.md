# SUIVI — Hardening & Recovery Claviger V1.1

## Checkpoint de reprise — 21 septembre 2026

**Branche active :** `feature/v11-hardening-recovery`  
**HEAD validé avant ce document :** `b93ef7ad20e06f1b1853ba9debb2402c5ac4371d`  
**Schéma SQLite courant :** V12  
**Audit de référence :** `08_AUDIT_HARDENING_RECOVERY_V1_1_2026-09-19.md`

Ce fichier est le **journal opérationnel de reprise** de la tranche
hardening/recovery.

Il ne remplace pas l'audit ni la roadmap globale :

- l'audit décrit les risques et contrats ;
- la roadmap décrit l'ordre général de fermeture de la V1.1 ;
- ce fichier indique **où le développement en est réellement**.

---

# 1. Règle de continuité inter-session

À chaque nouvelle sous-tranche de développement hardening :

1. vérifier le HEAD réel de la branche ;
2. mettre à jour ce fichier **avant de commencer le code** ;
3. marquer la sous-tranche comme `🔧 EN COURS` ;
4. noter son objectif et son gate de sortie ;
5. après implémentation et validation, passer son état à `✅ VALIDÉ` ;
6. noter les commits importants, tests ciblés / smoke réalisés et décisions
   d'architecture prises ;
7. indiquer clairement la prochaine sous-tranche prévue.

Ainsi, une nouvelle session doit pouvoir reprendre le chantier sans reconstruire
l'historique depuis les conversations.

## États utilisés

| État | Sens |
|---|---|
| ⏳ À FAIRE | sous-tranche planifiée mais non commencée |
| 🔧 EN COURS | développement démarré, gate non encore validé |
| 🧪 À VALIDER | code présent, validation développeur encore attendue |
| ✅ VALIDÉ | code + validation attendue terminés |
| ⛔ BLOQUÉ | décision ou incident empêchant de poursuivre proprement |

---

# 2. Vue d'ensemble hardening

| Tranche | Sujet | État |
|---|---|---|
| H1 | Sécurité DB et mode minimal | ✅ VALIDÉ |
| H2 | Mutations Discord partielles | 🧪 À VALIDER |
| H3 | Drift live restant | ⏳ À FAIRE |
| H4 | Last Known Good + backups | ⏳ À FAIRE |
| H5 | Matrice de panne + smoke multi-guild | ⏳ À FAIRE |

---

# 3. H1 — Sécurité DB et mode minimal

## H1.1 — Disponibilité ≠ intégrité

**État : ✅ VALIDÉ**

### Objectif

Empêcher Claviger de considérer une base comme `READY` uniquement parce que :

- le fichier existe ;
- SQLite accepte une connexion ;
- un `SELECT 1` fonctionne ;
- `PRAGMA user_version` est lisible.

### Contrat retenu

Le diagnostic distingue maintenant :

```text
MISSING
→ fichier absent

UNAVAILABLE
→ Claviger ne peut pas suffisamment accéder / inspecter la DB
→ la cause d'intégrité n'est pas prouvée

INTEGRITY_FAILED
→ SQLite fournit un signal explicite d'intégrité invalide
→ ou PRAGMA quick_check n'est pas OK

READY / MIGRATION_REQUIRED / TOO_NEW / UNINITIALIZED
→ seulement après validation d'intégrité
```

Claviger ne prétend donc pas connaître une cause qu'il n'a pas démontrée.

### Implémentation validée

- ajout de `DatabaseConnection.check_integrity()` ;
- contrôle via `PRAGMA quick_check` ;
- ajout de `DatabaseState.INTEGRITY_FAILED` ;
- classification de `SQLITE_CORRUPT` et `SQLITE_NOTADB` comme échec
  d'intégrité ;
- les autres erreurs empêchant le diagnostic restent `UNAVAILABLE` ;
- suppression du pré-filtre `is_available()` dans le chemin de statut lorsqu'il
  masquait les fichiers SQLite invalides ;
- lecture du `user_version` uniquement après validation d'intégrité ;
- diagnostic ADMIN explicite pour `INTEGRITY_FAILED` ;
- aucune commande lifecycle mutante proposée pour cet état ;
- protections supplémentaires dans les commandes déjà construites afin
  d'éviter une mutation si l'état a changé depuis le startup.

### Commits de la sous-tranche

```text
61f2d8903fbcc6c730f58c3a0cac36c563580e67
feat: fail closed on SQLite integrity errors

799b7b578d05eac17e8736afc1b7f3857a0cf14f
fix: distinguish SQLite corruption from unavailability

b93ef7ad20e06f1b1853ba9debb2402c5ac4371d
Ruff fix / validation développeur
```

### Validation

Tests ciblés exécutés et validés par le développeur après le correctif :

```text
tests/database/test_database_connection.py
tests/database/test_database_status.py
```

Le développeur a ensuite appliqué et pushé le Ruff fix.

### Résultat

`H1.1` est fermé.

La base du futur mode recovery sait désormais différencier :

```text
je ne peux pas savoir si la DB est saine
≠
j'ai la preuve que son intégrité n'est pas valide
```

---

## H1.2 — Contrat runtime normal / recovery snapshot / minimal

**État : ✅ VALIDÉ**

### Décisions déjà prises

Au moindre incident DB significatif :

1. les mutations dépendantes de la DB sont bloquées ;
2. l'état DB doit être recontrôlé afin d'éviter de déclencher un recovery sur
   un simple incident transitoire ;
3. l'owner est informé ;
4. si un Last Known Good snapshot valide existe, Claviger **propose** de passer
   dessus ;
5. le basculement snapshot n'est jamais automatique ;
6. si l'owner refuse le snapshot ou si le snapshot est invalide/inutilisable,
   Claviger passe en **mode minimal** ;
7. le snapshot reste read-only comme **état de configuration/recovery** et ne
   devient jamais la source de vérité persistante ; cela n'interdit pas les
   mutations de rôles membres sur Discord nécessaires aux questionnaires.

Hiérarchie cible :

```text
NORMAL
→ SQLite saine et autoritative

RECOVERY / SNAPSHOT
→ SQLite non fiable
→ Last Known Good explicitement accepté
→ configuration persistée figée
→ questionnaires métier maintenus
→ mutations de rôles membres Discord autorisées si Discord est sain

MINIMAL
→ DB non fiable et snapshot non choisi / inutilisable
→ dépendances métier réduites au strict minimum

HARD STOP
→ même le mode minimal ne peut pas fonctionner en sécurité
```

Cible V2.0 déjà décidée :

- en mode minimal, l'IA conversationnelle pourra rester disponible ;
- uniquement pour l'owner et un rôle de secours dédié ;
- cette fonctionnalité IA n'est pas à implémenter prématurément dans la V1.1.

### Implémentation réalisée

Commit principal :

```text
e240af427f440c38892990b5ca33d9a5b28f6ada
feat: model degraded application runtime state
```

La tranche a :

- introduit `ApplicationRuntimeState` ;
- introduit les modes `NORMAL`, `RECOVERY`, `MINIMAL`, `HARD_STOP` ;
- distingué l'ownership DB `VALID`, `UNBOUND`, `MISMATCH`,
  `NOT_EVALUATED` ;
- remplacé le couple implicite `database_status + database_operational` du
  runtime global par un état applicatif explicite ;
- ajouté `refresh_application_runtime_state()` comme point central de recheck ;
- ajouté un second contrôle immédiat lorsqu'un accès ownership échoue
  temporairement ;
- conservé `NORMAL` uniquement pour une DB READY avec ownership VALID ;
- fait dégrader un mismatch vers `MINIMAL` au lieu d'arrêter Discord ;
- conservé le fail-closed : aucun workflow DB normal en mode minimal ;
- empêché l'exposition de `database bind` lorsque l'ownership est MISMATCH ;
- adapté `config-server` pour expliquer le mismatch sans proposer de takeover ;
- conservé les erreurs d'identité Discord comme hard stop réel.

Le **snapshot Last Known Good lui-même reste H4**. Les valeurs `RECOVERY` et
`HARD_STOP` font partie du vocabulaire runtime préparé par H1.2, mais la
sélection/lecture du snapshot n'est pas implémentée dans cette tranche.

Décision fonctionnelle complémentaire pour la V1.3 :

- les mutations structurelles officielles (rôles, salons, permissions,
  workflows et opérations d'administration similaires) doivent passer par les
  commandes/services Claviger plutôt que par des permissions Discord accordées
  directement aux modérateurs ou utilisateurs de confiance ;
- l'owner reste l'exception disposant des droits Discord natifs nécessaires ;
- en mode `RECOVERY / SNAPSHOT`, Claviger doit refuser ces mutations
  structurelles et rester essentiellement en lecture/diagnostic ;
- ce garde-fou permet au service de continuer à fonctionner pendant l'analyse
  d'un incident DB sans forcer une réparation précipitée.

### Validation

La sous-tranche H1.2 a été validée localement par le développeur le
21 septembre 2026.

Tests ciblés de référence :

```text
tests/runtime/test_bot.py
tests/runtime/test_bot_multi_guild_lifecycle.py
tests/commands/admin/test_database_command_availability.py
tests/commands/admin/test_config_server.py
```

### Gate H1.2

- runtime NORMAL lorsque DB READY + ownership valide ;
- runtime MINIMAL pour DB non opérationnelle, ownership absent ou mismatch ;
- aucune mutation métier DB en mode MINIMAL ;
- commandes de recovery toujours accessibles ;
- identité Discord invalide / absente reste un hard stop ;
- tests runtime ciblés verts.

---

# 4. H2 — Mutations Discord partielles

**État : 🧪 À VALIDER**

## Problème traité

Le preflight garantit que toutes les ressources prévues sont valides **avant**
la première mutation Discord. Il ne peut cependant pas rendre atomiques
plusieurs appels Discord successifs.

Exemple :

```text
retirer rôle A       ✅
retirer rôle B       ✅
ajouter rôle C       ❌ erreur Discord / réseau
```

Le membre possède alors un état réel partiellement modifié.

## Contrat retenu

H2 adopte une stratégie de **réconciliation**, pas de rollback automatique.

```text
mutation partielle détectée
→ conserver la liste exacte des changements déjà réussis
→ ne pas tenter de rollback Discord automatique
→ signaler explicitement l'état partiel
→ demander de relancer le questionnaire
→ rebuild frais de l'état réel Discord
→ nouveau planning
→ nouveau preflight
→ réconciliation vers l'état désiré
```

Raison : un rollback est lui-même une nouvelle série d'appels réseau susceptible
d'échouer et d'aggraver l'incertitude.

En cas de process kill/restart entre deux mutations, aucun handler Python ne
peut garantir un report immédiat. Le recovery fonctionnel reste le même :
relancer le questionnaire reconstruit l'état actuel du membre depuis Discord,
sans supposer que l'exécution précédente s'est terminée.

## Implémentation réalisée

Commit principal :

```text
89f5aba26ab637bf91870b142c7d9ed339144a03
feat: report partial workflow role mutations
```

La tranche a :

- conservé `WorkflowRoleExecutionPartialError` comme contrat d'exécution
  partielle ;
- ajouté des tests dédiés lorsqu'une panne survient pendant les removals ;
- ajouté des tests lorsqu'une panne survient après removal puis pendant les
  additions ;
- vérifié qu'un échec sur la toute première mutation reste un échec normal et
  n'est pas faussement classé « partiel » ;
- ajouté un traitement UI spécifique aux mutations partielles ;
- ajouté un report `workflow.questionnaire.partial_failure` contenant les
  `added_role_ids`, `removed_role_ids` et la cause d'origine ;
- remplacé le message générique par une consigne explicite de relance et
  réconciliation ;
- confirmé qu'aucun rollback compensatoire automatique n'est effectué.

Le mécanisme de recovery repose sur le comportement déjà existant du
`WorkflowQuestionnaireCoordinatorService` : chaque nouvelle soumission rebuild
l'état persistant et les rôles réels du membre avant de recalculer le plan.

## Validation ciblée à exécuter

```text
tests/services/workflows/test_workflow_role_executor_service.py
tests/ui/workflows/test_workflow_questionnaire_partial_failure.py
tests/services/workflows/test_workflow_questionnaire_coordinator_service.py
```

## Gate H2

- tests dédiés sur mutation partielle pendant les removals et additions ;
- `WorkflowRoleExecutionPartialError` expose les mutations réellement réussies ;
- UI distingue une mutation partielle d'un échec sans effet de bord ;
- report admin contient les IDs ajoutés / retirés effectivement ;
- message utilisateur n'annonce jamais un succès complet après mutation partielle ;
- aucune compensation automatique ;
- la relance du questionnaire reste le chemin de réconciliation.

---

# 5. H3 — Drift live restant

**État : ⏳ À FAIRE**

Principaux sujets déjà identifiés :

- rôle IA global disparu côté workflow consumer ;
- fallback Discord lorsque la config ADMIN persistée est complète mais que le
  forum réel est cassé ;
- vérification des autres ressources live importantes sans transformer la
  readiness persistée en mega-service.

---

# 6. H4 — Last Known Good et backups

**État : ⏳ À FAIRE**

Décisions déjà prises :

### Snapshot Last Known Good

```text
SQLite = source de vérité
snapshot = dernier état cohérent connu / fallback recovery
```

Le snapshot doit être :

- versionné ;
- atomique ;
- lisible sans SQLite ;
- read-only pour la configuration et les écritures persistantes normales ;
- insuffisant seul pour autoriser une évolution de configuration ;
- suffisamment riche pour permettre aux questionnaires existants de continuer
  à fonctionner.

### Contrat de service en mode snapshot

Le mode snapshot doit préserver le cœur métier de Claviger :

```text
/membre, /adult et futurs questionnaires
→ restent accessibles

lecture du Last Known Good
→ calcule les accès attendus

Discord sain
→ peut recevoir les mutations de rôles membres

création/modification de workflows, rôles structurels, salons, permissions
→ refusée tant que SQLite n'est pas fiable
```

Pendant cette fenêtre, Discord devient la **réalité opérationnelle temporaire**
pour les rôles membres gérés par Claviger. La date d'entrée en recovery doit être
connue afin de borner la période à réconcilier.

Lors du retour en mode NORMAL, le futur moteur de résilience devra pouvoir
réconcilier la persistence membre avec les rôles Discord observés pendant la
fenêtre snapshot. La cible envisagée est un contrôle vers **22 h 30** ou au
premier créneau sûr après retour de SQLite ; si SQLite reste indisponible, la
réconciliation est différée.

Un fichier/journal hors SQLite (par exemple JSON atomique) n'est **pas** la voie
normale. Il n'est envisagé qu'en dernier filet lorsqu'on cumule :

```text
mode snapshot
+
échec de mutation/communication Discord
```

et uniquement pour les membres/opérations réellement en anomalie.

### Backup SQLite

Politique cible :

```text
vers 23 h
→ backup SQLite cohérent
→ validation
→ copie NAS confirmée
→ rotation
→ conserver seulement les 2 dernières sauvegardes validées
```

La plus ancienne n'est supprimée qu'après succès complet de la nouvelle.

Le même moteur doit servir aux backups obligatoires avant migration et
déploiement.

---

# 6.1 Orientation post-V1.1 — résilience des rôles membres

Un développement dédié est désormais prévu après fermeture de la V1.1 pour
conserver et réconcilier l'état attendu des rôles membres gérés par Claviger.

La décision de versionnage est volontairement différée :

```text
fin V1.1
→ évaluer l'importance / le volume du moteur de résilience
→ soit l'intégrer à la future V1.3
→ soit lui consacrer une version propre
→ et décaler la V1.3 actuelle en V1.4 si nécessaire
```

Document de cadrage :

`documentations/development/RESILIENCE_ETAT_ROLES_MEMBRES_POST_V1_1.md`

Ce sujet ne doit pas être glissé silencieusement dans H2/H4 : H4 doit seulement
fournir les primitives recovery nécessaires.

---

# 7. H5 — Matrice de panne et smoke multi-guild

**État : ⏳ À FAIRE**

À fermer avant production :

- panne DB ;
- drift Discord ;
- restart / retour après incident ;
- Guild A cassée volontairement ;
- Guild B toujours fonctionnelle ;
- validation Linux / Succumbrae des mécanismes de recovery.

---

# 8. Prochaine action

H1 est fermé :

```text
H1.1 — disponibilité ≠ intégrité       ✅ VALIDÉ
H1.2 — runtime normal/minimal          ✅ VALIDÉ
H1   — sécurité DB et mode minimal     ✅ VALIDÉ
```

Tranche active :

```text
H2 — mutations Discord partielles
```

Le code H2 est présent et la tranche est en **🧪 À VALIDER**.

Prochaine action :

1. exécuter les tests ciblés H2 ;
2. corriger toute régression éventuelle ;
3. après validation locale, passer H2 en `✅ VALIDÉ` ;
4. préparer ensuite H3 — drift live restant.
