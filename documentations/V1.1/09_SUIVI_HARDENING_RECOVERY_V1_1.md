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
| H1 | Sécurité DB et mode minimal | 🔧 EN COURS |
| H2 | Mutations Discord partielles | ⏳ À FAIRE |
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

**État : 🧪 À VALIDER**

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
7. le snapshot reste read-only côté recovery et ne devient jamais la source de
   vérité persistante.

Hiérarchie cible :

```text
NORMAL
→ SQLite saine et autoritative

RECOVERY / SNAPSHOT
→ SQLite non fiable
→ Last Known Good explicitement accepté
→ lecture / recovery seulement

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

### Validation ciblée à exécuter

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

**État : ⏳ À FAIRE**

Contrat à fermer :

- test dédié `WorkflowRoleExecutionPartialError` ;
- reporting des IDs réellement ajoutés / retirés ;
- décision explicite rollback compensatoire vs réconciliation ;
- interruption/restart pendant une mutation ;
- aucune fausse confirmation de succès.

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
- read-only en recovery ;
- insuffisant seul pour autoriser les mutations persistantes normales.

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

Sous-tranche active :

```text
H1.2 — contrat runtime normal / recovery snapshot / minimal
```

Le HEAD a été vérifié et la tranche est officiellement en cours.

Prochaine action immédiate :

1. introduire l'état runtime explicite ;
2. centraliser l'évaluation DB / ownership ;
3. préserver les commandes de recovery en mode minimal ;
4. adapter les tests runtime ciblés.
