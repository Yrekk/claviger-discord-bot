# AUDIT — Hardening & Recovery Claviger V1.1

## État au 19 septembre 2026

**Branche auditée :** `feature/v11-hardening-recovery`  
**HEAD de référence :** `6ba15319901932945c3ae66ad3313121f746ac6e`  
**Schéma SQLite courant :** V12  
**Objet :** inventaire factuel du comportement actuel avant toute nouvelle tranche de durcissement.

---

# 1. But du document

Cette note sert de point de départ à la tranche **hardening / recovery** de la V1.1.

Le but n'est pas de proposer immédiatement des correctifs, mais de distinguer clairement :

- ce qui est déjà robuste dans le code actuel ;
- ce qui est déjà couvert par des tests automatisés ;
- ce qui est protégé partiellement ;
- ce qui reste absent ;
- ce qui mérite une décision d'architecture avant implémentation ;
- les smoke tests réels à prévoir ensuite.

Ce document ne remplace pas :

- la roadmap V1.1 ;
- les tests automatisés ;
- les smoke tests Discord ;
- le futur plan de déploiement Linux.

Il constitue l'**audit de référence de la résilience V1.1** avant correction.

---

# 2. Légende

| État | Signification |
|---|---|
| ✅ | protection déjà présente et cohérente dans le code actuel |
| 🟡 | protection partielle ou comportement correct mais encore incomplet |
| ❌ | mécanisme attendu non implémenté |
| 🔬 | comportement à confirmer par smoke réel |
| 📌 | décision d'architecture à prendre avant code |

Priorités proposées pour organiser la tranche :

| Priorité | Sens |
|---|---|
| **P0** | sécurité / intégrité : doit être tranché avant production |
| **P1** | robustesse importante : à fermer dans la V1.1 |
| **P2** | amélioration opérationnelle utile mais non bloquante seule |

---

# 3. Résumé exécutif

Le socle actuel est déjà nettement plus robuste que ne le suggère le mot « hardening ».

Les protections suivantes sont déjà structurantes :

- base absente ou indisponible détectée sans création automatique pendant le startup ;
- schéma trop ancien / trop récent identifié explicitement ;
- migrations SQLite appliquées transactionnellement, avec rollback en cas d'échec ;
- ownership de la DB lié à l'application Discord et validé fail-closed ;
- mode maintenance lorsque la DB n'est pas opérationnelle ;
- runtime et verrous séparés par guild ;
- guild indisponible invalidée puis reconstruite à son retour ;
- ADMIN réinspecté face à l'état Discord réel avant les commandes administratives ;
- configuration de workflow reconciliée avant provisioning ;
- découverte catalogue basée sur l'état Discord réel ;
- targets disparues marquées comme non disponibles en BDD au lieu d'être utilisées aveuglément ;
- reconstruction fraîche du questionnaire avant soumission ;
- rejet des formulaires devenus obsolètes ;
- preflight de tous les rôles avant la première mutation Discord ;
- détection explicite d'une exécution partielle si Discord échoue en cours de mutation ;
- reporting best-effort : la panne d'un reporter n'arrête pas les autres.

Les principaux écarts identifiés sont :

1. **pas de contrôle d'intégrité SQLite réel** au-delà de l'ouverture, `SELECT 1` et de la lecture de `user_version` ;
2. **aucun snapshot applicatif de recovery** dans le code actuel ;
3. **pas de backup opérationnel intégré** avant migration/déploiement ;
4. **mutation Discord partielle détectée mais insuffisamment exploitée et non couverte par un test dédié** ;
5. **fallback Discord du reporting incomplet en cas de drift ADMIN** : une config persistée complète mais un forum supprimé peut faire échouer le reporter forum tandis que le reporter DM s'abstient ;
6. certains drifts, notamment le **rôle IA global disparu**, peuvent dégrader le comportement avant qu'un diagnostic administratif soit lancé ;
7. le runtime ne possède pas encore de stratégie explicite de **recovery après perte de DB**, ni de distinction forte entre première installation et DB de production disparue.

## 3.1 Décisions actées après lecture de l'audit

Les décisions suivantes sont désormais retenues pour la suite de la tranche :

### Mode minimal

Le **mode minimal** n'est pas seulement un mode maintenance temporaire de V1.1.
Il constitue la cible de survie dégradée de Claviger :

```text
mode normal
→ fonctionnalités métier complètes

incident sérieux mais runtime encore sûr
→ mode minimal
→ application encore vivante
→ mutations métier normales désactivées
→ diagnostic / recovery disponibles

incident rendant même le mode minimal non fiable
→ hard stop
```

La conception V1.1 doit préparer cette séparation sans implémenter prématurément
les fonctionnalités IA de V2.0.

À terme, en **V2.0**, l'IA conversationnelle devra pouvoir continuer à répondre
en mode minimal, mais uniquement :

- à l'owner ;
- aux membres possédant un rôle de secours explicitement dédié.

Ce chemin minimal devra dépendre du moins possible de la chaîne métier normale
et ne devra jamais contourner les règles de sécurité de la DB principale.

### Snapshot Last Known Good

Le snapshot est confirmé comme **fallback applicatif** lorsqu'une DB principale
rencontre un problème.

Il reste toutefois secondaire :

```text
SQLite = source de vérité
snapshot = dernier état cohérent connu / fallback de recovery
```

Le snapshot ne doit pas devenir une deuxième DB maîtresse et ne suffit pas, à
lui seul, à autoriser les mutations persistantes normales.

### Backup opérationnel SQLite

Un système de backup automatisé fait désormais partie de cette tranche.

Cible retenue :

- stockage durable sur le NAS, dans un emplacement dédié aux sauvegardes DB ;
- sauvegarde nocturne vers **23 h** ;
- **deux sauvegardes validées maximum** conservées en rotation ;
- création d'une nouvelle sauvegarde cohérente SQLite ;
- validation de la sauvegarde avant promotion ;
- confirmation de la copie NAS ;
- suppression de la plus ancienne **uniquement après succès complet** ;
- si la nouvelle sauvegarde échoue, les deux sauvegardes précédentes sont
  conservées intactes.

Les backups pré-migration et pré-déploiement restent obligatoires. Le même
moteur de sauvegarde doit être réutilisé ; la relation exacte entre ces backups
ponctuels et la rotation nocturne sera décidée lors de l'implémentation.

---

# 4. Base SQLite — disponibilité et état

## 4.1 Base absente

### État actuel

✅ `DatabaseStatusService.check()` teste d'abord l'existence du fichier.

Une DB absente est classée :

```text
DatabaseState.MISSING
```

Le startup ne l'initialise pas automatiquement.

Le runtime normal est désactivé et Claviger expose les commandes de maintenance pertinentes.

Le repository d'ownership possède également une garde explicite :

```text
_ensure_database_exists()
```

afin d'éviter qu'un simple accès repository crée implicitement une nouvelle base SQLite.

### Point positif

Une perte du fichier DB ne provoque donc pas, à elle seule, la création silencieuse d'une nouvelle base.

### Limite

🟡 La commande manuelle `database initialize` reste proposée dans l'état `MISSING`.

C'est correct pour une première installation, mais le code ne sait pas encore distinguer :

```text
première installation légitime
vs
volume Docker non monté
vs
fichier production supprimé
vs
mauvais chemin de DB
```

Un propriétaire doit toujours agir explicitement, donc il n'y a pas de destruction automatique, mais une initialisation manuelle sur un mauvais volume reste possible.

### Priorité

**P0 — décision à prendre avec le futur snapshot / marqueur d'installation.**

---

## 4.2 Base indisponible

### État actuel

✅ `DatabaseConnection.connect()` transforme les erreurs d'ouverture en `DatabaseUnavailableError`.

✅ `DatabaseConnection.is_available()` vérifie :

```text
fichier présent
→ connexion SQLite
→ SELECT 1
```

✅ `DatabaseStatusService` classe alors la base en :

```text
DatabaseState.UNAVAILABLE
```

✅ le startup bascule en mode maintenance au lieu d'activer les workflows persistants.

### Limite

🟡 Le statut DB applicatif est principalement établi au startup.

Si la DB devient indisponible **pendant** que le bot fonctionne, les repositories échouent correctement, mais il n'existe pas encore de mécanisme global qui transforme automatiquement le runtime entier en état maintenance jusqu'au retour de la DB.

Le comportement actuel est donc :

```text
DB READY au startup
→ runtime normal
→ DB tombe ensuite
→ les opérations DB échouent individuellement
→ logs / reporting selon le chemin concerné
```

et non :

```text
DB tombe
→ état applicatif global immédiatement invalidé
→ commandes métier globalement désactivées
```

### Décision retenue

Le runtime doit viser une **dégradation explicite vers un mode minimal** plutôt
qu'une simple succession d'erreurs indépendantes, tant que ce mode peut rester
sûr.

Pour la V1.1, cela signifie au minimum préparer un état runtime clairement
identifiable et fermer les mutations métier normales. La capacité IA
conversationnelle réservée à l'owner et au rôle de secours appartient à la
cible V2.0, pas à cette tranche fonctionnelle.

---

## 4.3 Corruption SQLite

### État après H1.1

✅ `DatabaseStatusService` ne se contente plus de l'ouverture et de
`SELECT 1`.

Après avoir confirmé que le fichier existe et reste accessible, il exécute
désormais :

```sql
PRAGMA quick_check;
```

avant de lire le `user_version`.

Un échec explicite du contrôle ou un résultat différent de `ok` produit :

```text
DatabaseState.INTEGRITY_FAILED
```

et non `READY`.

Le runtime métier reste donc fermé puisque seul `READY` peut être considéré
opérationnel.

La commande de statut expose cet état comme **Intégrité invalide** et recommande
de ne pas modifier la base en place. Les commandes de cycle de vie mutantes ne
sont pas exposées pour cet état.

### Limite restante

🟡 `PRAGMA quick_check` est volontairement le contrôle courant léger. Le futur
moteur de backup devra également valider la sauvegarde produite avant rotation.

La stratégie de restauration/fallback appartient aux tranches snapshot/backup
suivantes.

---

## 4.4 Schéma trop ancien / trop récent

### État actuel

✅ Les états sont distingués :

```text
UNINITIALIZED
MIGRATION_REQUIRED
READY
TOO_NEW
```

✅ une DB plus récente que la version du bot n'est pas modifiée automatiquement.

✅ `DatabaseSchema.initialize()` et `migrate()` refusent également un schéma trop récent.

✅ les commandes de maintenance exposées sont filtrées selon l'état réel.

### Priorité

Aucune correction métier évidente.

**🔬 Smoke Linux recommandé avant production.**

---

# 5. Migrations

## 5.1 Atomicité

### État actuel

✅ Chaque migration est entourée par :

```text
BEGIN IMMEDIATE
→ statements
→ éventuel transfert de données
→ PRAGMA user_version
→ COMMIT
```

En cas d'erreur ou d'annulation :

```text
ROLLBACK
→ exception propagée
```

Le code capture volontairement `BaseException` à cette frontière afin de ne pas laisser une migration partielle validée.

### Couverture existante

Les tests couvrent notamment :

- migration depuis plusieurs versions historiques ;
- conservation de données ;
- refus d'une DB trop récente ;
- refus d'une DB non initialisée ;
- refus d'une migration déjà à jour.

### Limite

🟡 Une montée de plusieurs versions est atomique **par version**, pas dans une transaction englobant toute la chaîne.

C'est un comportement raisonnable : si V9 réussit et V10 échoue, le `user_version` reflète V9 et une exécution ultérieure peut reprendre.

Ce point n'est pas identifié comme un défaut.

---

## 5.2 Backup avant migration

### État actuel

❌ Aucun mécanisme opérationnel de backup pré-migration n'a été identifié dans le runtime audité.

La roadmap distingue déjà correctement :

```text
snapshot applicatif
≠
backup opérationnel
```

### Priorité

**P0 avant déploiement Succumbrae.**

Le backup opérationnel doit probablement appartenir à la chaîne de déploiement plutôt qu'au métier du bot.

---

# 6. Ownership de la base

## État actuel

✅ Une DB possède au maximum un owner applicatif via :

```text
database_ownership
singleton_id = 1
application_id
```

✅ `bind()` :

- lie une DB non liée ;
- est idempotent pour la même application ;
- refuse une autre application.

✅ `validate()` échoue si :

- la DB n'est pas liée ;
- la DB appartient à une autre application.

✅ les tests couvrent les trois cas.

## Comportement startup

Une DB `READY` mais non liée entraîne un runtime non opérationnel et permet le chemin de récupération `database bind`.

En revanche, un **ownership mismatch** lève actuellement une exception pendant le `setup_hook`.

Le test :

```text
test_setup_hook_rejects_database_owned_by_another_application
```

confirme que ce comportement est intentionnel dans l'état actuel.

## Analyse

✅ Sécurité : fail-closed fort.

### Décision retenue

Lorsqu'il est techniquement possible de rester vivant sans faire confiance à la
DB concernée, Claviger doit privilégier le **mode minimal** au hard stop complet.

Un ownership mismatch reste cependant **fail-closed pour la DB** :

- aucune mutation métier normale ;
- aucun rebind automatique ;
- aucune prise de possession silencieuse ;
- uniquement les surfaces de diagnostic/recovery explicitement sûres.

Si le runtime ne peut pas garantir ce périmètre minimal, le hard stop reste
préférable.

### Priorité

**P1 — adapter le startup à ce contrat sans affaiblir l'ownership.**

---

# 7. Runtime multi-guild et lifecycle

## 7.1 Isolation des états

### État actuel

✅ `guild_runtime_states` est indexé par `guild_id`.

✅ les locks de configuration sont également dédiés par guild.

✅ une configuration de guild n'est pas réutilisée comme état global.

✅ `on_ready()` configure chaque guild disponible indépendamment.

Une exception sur une guild est loggée dans sa boucle sans empêcher volontairement le passage aux autres guilds.

### Couverture existante

Les tests runtime couvrent notamment :

- plusieurs guilds au `on_ready` ;
- guilds indisponibles ignorées ;
- isolation de runtime ;
- join / available ;
- command tree séparé.

### Priorité

Aucun défaut architectural identifié à ce stade.

**🔬 Le smoke réel sur une deuxième guild reste nécessaire.**

---

## 7.2 Guild unavailable / available

### État actuel

✅ `on_guild_unavailable` retire uniquement l'état runtime de la guild concernée.

✅ `on_guild_available` reconstruit cette guild.

✅ un lock évite deux reconstructions concurrentes lors du startup.

✅ les tests vérifient le chevauchement `on_ready` / `on_guild_available`.

### Point à confirmer

🔬 Smoke réel :

```text
Guild A unavailable
→ Guild B continue
→ Guild A revient
→ Guild A reconstruite
→ aucune contamination
```

---

## 7.3 Guild retirée

### État actuel

✅ `on_guild_remove` :

- retire son runtime ;
- clear son arbre local de commandes ;
- ne supprime pas automatiquement ses données persistées.

Cette conservation de la DB est prudente : quitter une guild ne détruit pas automatiquement son historique/configuration.

### Décision future éventuelle

📌 Une politique de purge des guilds définitivement abandonnées pourra être définie plus tard, mais ce n'est pas un sujet de recovery V1.1.

---

# 8. ADMIN — drift Discord

Cette partie est déjà particulièrement robuste.

## 8.1 Discovery et reconciliation

### État actuel

✅ la configuration persistée est comparée à l'état Discord réel.

Les cas détectés incluent :

- catégorie ADMIN supprimée ;
- channel configuré manquant ;
- mauvais type de channel ;
- catégorie ou child visible à `@everyone` ;
- bot incapable de voir la catégorie ;
- bot incapable d'utiliser un channel ;
- activity/error forum incohérents ;
- plusieurs catégories candidates ambiguës.

La reconciliation refuse les remplacements silencieux quand plusieurs choix sont possibles.

---

## 8.2 Guard des commandes ADMIN

### État actuel

✅ `GuildAdminCommandGroup` effectue une **inspection fraîche** du routing avant les commandes.

Si le routing est encore sain :

```text
commande ADMIN
→ uniquement dans admin-commands
```

Si la config a drifté ou si l'inspection échoue :

```text
commandes normales ADMIN
→ refusées

recovery commands
→ database
→ restart
→ config-server
→ config
```

restent utilisables.

### Conclusion

✅ La suppression d'un salon ADMIN ne repose pas uniquement sur la readiness calculée au startup.

C'est une bonne base de recovery.

---

# 9. Configuration des workflows — drift avant provisioning

## État actuel

✅ la reconciliation de configuration vérifie avant provisioning :

- catégorie encore existante ;
- salon encore existant ;
- salon appartenant à la bonne catégorie ;
- permissions de réparation disponibles ;
- rôle principal encore manipulable ;
- permission de créer channels / rôles si la config demande une création.

✅ les sélections obsolètes échouent fail-closed.

### Limite

Ce mécanisme concerne surtout la **configuration / reconfiguration**.

Une fois le workflow persisté et les commandes runtime construites, le runtime ne recalcule pas une readiness structurelle complète du workflow avant chaque commande.

La sécurité reste cependant couverte par plusieurs couches plus ciblées décrites ci-dessous.

---

# 10. Catalogues — drift des rôles et salons

## 10.1 Discovery réelle

### État actuel

✅ chaque préparation de questionnaire resynchronise les catalogues liés au workflow.

Le snapshot observe :

- rôles Discord ;
- manageability par rapport au rôle du bot ;
- text channels ;
- forum channels ;
- mappings explicites rôle → contenu.

✅ si `guild.me` est introuvable, la discovery échoue au lieu d'inventer un état.

---

## 10.2 Mapping ambigu ou absent

### État actuel

Pour qu'une target soit construite :

```text
exactement 1 salon/forum explicitement visible
```

Si le rôle possède :

```text
0 mapping
ou
> 1 mapping
```

la target n'est pas considérée comme exploitable.

✅ un rôle précédemment synchronisé mais désormais absent du discovery est conservé en BDD avec :

```text
discord_present = 0
role_manageable = 0
channel_present = 0
mapping_valid = 0
```

Le moteur dispose donc de l'information historique nécessaire pour ne pas transformer silencieusement une ancienne paire en singleton sain.

### Conséquence

✅ une paire IA/no-IA dont une target historiquement connue devient indisponible est rejetée par le planner au lieu d'appliquer une demi-paire.

### Couverture

La discovery possède déjà des tests sur :

- mapping unique ;
- mapping multiple ;
- types de channels non supportés ;
- rôle non manipulable ;
- rôle Discord-managed ;
- absence de `guild.me`.

### À compléter

🔬 Smoke réel de suppression/ambiguïté pendant un questionnaire.

---

# 11. Formulaires stale

## État actuel

✅ la soumission ne fait pas confiance au formulaire ouvert.

Au submit :

```text
rebuild workflow
→ resync catalogues
→ relire rôles membre
→ relire préférence IA
→ reconstruire questionnaire
→ comparer options visibles avec snapshot soumis
```

Si les catalogues ou options ne correspondent plus :

```text
WorkflowQuestionnaireSubmissionError
```

avant toute mutation.

### Conclusion

✅ La protection stale-state est bien architecturée.

### Smoke restant

🔬 ouvrir un formulaire, modifier/supprimer une ressource Discord, puis valider.

---

# 12. Rôle principal et rôles catalogue disparus

## Rôle catalogue disparu

Le resync catalogue l'invalide avant planning.

✅ fail-closed.

## Rôle catalogue devenu non manipulable

La discovery met `role_manageable = false`.

✅ la target devient indisponible.

## Rôle principal disparu après configuration

Le rôle principal reste référencé par ID dans le workflow.

Au moment d'exécuter le plan :

```text
guild.get_role(primary_role_id)
→ None
→ WorkflowRoleNotFoundError
```

avant la première mutation grâce au preflight.

✅ fail-closed.

## Rôle principal devenu non manipulable

Le preflight appelle `is_role_manageable()`.

✅ fail-closed avant la première mutation.

---

# 13. Rôle IA global disparu

## État actuel

La configuration IA persistée contient :

```text
ai_enabled
ai_role_id
```

Le planner considère la fonctionnalité IA techniquement configurée dès lors que :

```text
ai_enabled = true
AND ai_role_id != null
```

L'état utilisateur est ensuite déduit de la présence de cet ID dans les rôles du membre.

## Cas owner IA

Si l'utilisateur tente d'activer l'IA et que le rôle a disparu, le rôle global entre dans le plan puis le preflight échoue.

✅ aucun ajout partiel avant ce refus.

## Cas workflow non-owner

🟡 Un workflow consommateur peut interpréter l'absence du rôle sur le membre comme une préférence IA inactive, même si la cause réelle est que **le rôle global n'existe plus dans Discord**.

Le diagnostic administratif peut révéler le drift, mais le runtime questionnaire ne valide pas explicitement l'existence du rôle IA avant de consommer l'état.

### Risque

Dégradation silencieuse vers le comportement sans IA sur les workflows non-owner.

### Priorité

**P1 — ajouter une validation live de la ressource IA globale ou un état explicite « IA configurée mais indisponible ».**

---

# 14. Preflight des mutations de rôles

## État actuel

✅ `WorkflowRoleExecutorService` collecte toutes les IDs prévues avant mutation.

Pour chaque rôle :

```text
guild.get_role()
→ existe ?
→ pas @everyone ?
→ pas Discord-managed ?
→ sous le top role du bot ?
```

Si un seul rôle est invalide :

```text
aucune mutation Discord n'a encore eu lieu
```

### Couverture existante

Le test :

```text
test_executor_preflights_all_roles_before_first_mutation
```

confirme qu'un rôle invalide en fin de plan empêche également une première mutation pourtant valide.

### Conclusion

✅ Très bonne base de sécurité.

---

# 15. Mutation Discord partielle

## État actuel

Le preflight ne peut pas empêcher une erreur réseau/API survenant **après** le début de l'exécution.

L'executor applique actuellement :

```text
removals
→ additions
```

et conserve en mémoire les mutations effectivement réussies.

Si une exception arrive après au moins une mutation :

```text
WorkflowRoleExecutionPartialError
```

est levée avec :

```text
added_role_ids
removed_role_ids
```

### Point positif

✅ le code distingue déjà :

```text
échec avant mutation
vs
échec après mutation partielle
```

C'est exactement l'information nécessaire pour un recovery sérieux.

### Limites

🟡 aucun test dédié de mutation partielle n'a été identifié dans
`test_workflow_role_executor_service.py`.

🟡 la couche UI attrape actuellement l'exception comme une exception générique et reporte seulement :

```text
WorkflowRoleExecutionPartialError:
Workflow role execution stopped after partial Discord mutation.
```

Les listes `added_role_ids` / `removed_role_ids` ne sont donc pas encore exploitées dans le report utilisateur/admin.

❌ aucun rollback automatique n'est implémenté.

### Décision d'architecture

📌 Ne pas choisir automatiquement « rollback systématique ».

Le modèle Claviger repose déjà sur la réconciliation d'un état désiré. Un rollback réseau peut lui-même échouer et aggraver l'incertitude.

La tranche doit comparer au minimum :

1. **rollback compensatoire best-effort** ;
2. **aucun rollback, mais report détaillé + prochaine réconciliation corrective** ;
3. **journal d'opération / recovery ciblé**.

### Priorité

**P0 — définir le contrat et couvrir le cas par tests.**

---

# 16. Restart

## État actuel

✅ le restart demandé depuis Discord est différé jusqu'à la fin de
`app_command_completion`, évitant de démonter discord.py pendant que la commande se termine.

✅ les signatures d'arbres de commandes sont conservées pour éviter des sync Discord inutiles après restart.

✅ les tests couvrent :

- attente de completion ;
- token de restart ;
- absence de déclenchement par une autre completion ;
- réutilisation des signatures par guild.

## Limite

🟡 il n'existe pas de journal persistant d'une mutation workflow en cours.

Un restart/process kill au milieu d'une série d'appels Discord peut donc laisser un état partiel analogue à une erreur réseau.

Le prochain questionnaire pourra reconstruire l'état réel du membre, mais il n'existe pas encore de procédure dédiée annonçant :

```text
une opération a été interrompue
→ voici ce qui était attendu
→ voici ce qui doit être réconcilié
```

### Priorité

**P1**, à traiter avec le contrat de mutation partielle.

---

# 17. Reporting et observabilité

## 17.1 Isolation des reporters

### État actuel

✅ `ReportService` exécute chaque reporter indépendamment.

Une erreur dans un reporter :

- est loggée ;
- n'empêche pas les reporters suivants d'être exécutés ;
- ne remonte pas comme erreur métier vers l'opération d'origine.

C'est le comportement voulu pour un reporting best-effort.

---

## 17.2 Fallback DM de bootstrap

### État actuel

✅ tant que la configuration ADMIN n'est pas complète, un incident actor-scoped peut être envoyé en DM.

✅ si la DB est indisponible pendant la résolution de la config ADMIN, le reporter DM considère le routing non fiable et tente le fallback DM.

### Drift problématique

🟡 Si la configuration persistée est **complète**, le reporter DM considère que le reporting ADMIN a pris le relais et s'abstient.

Or le reporter forum peut ensuite échouer parce que :

- forum supprimé ;
- ID ne résout plus ;
- channel devenu du mauvais type ;
- permissions retirées.

Dans ce scénario :

```text
config DB = complète
→ DM reporter s'abstient

forum Discord = cassé
→ forum reporter échoue

reste
→ Python logger
```

L'incident n'est donc plus garanti d'atteindre un humain via Discord.

### Priorité

**P1 — faire dépendre le fallback de la capacité réelle à router, ou établir une stratégie équivalente.**

---

# 18. Readiness persistée vs drift live

## État actuel

`GuildConfigurationReadinessService` est volontairement documenté comme un service de **readiness persistée uniquement**.

Il ne prétend pas vérifier le drift Discord.

✅ cette séparation est explicite et cohérente.

Pour ADMIN, le drift live est compensé par l'inspection fraîche du command group.

Pour les workflows, le runtime se repose ensuite sur :

- resync catalogue ;
- rebuild questionnaire ;
- stale check ;
- preflight rôles.

### Point à garder

Il ne faut pas transformer `GuildConfigurationReadinessService` en mega-service vérifiant Discord à chaque appel.

Le hardening doit continuer à séparer :

```text
readiness persistée
≠
inspection live
≠
preflight mutation
```

---

# 19. Snapshot applicatif

## État actuel

❌ Aucun module de snapshot/recovery n'a été identifié dans `src/claviger`.

❌ aucun test snapshot n'est présent dans l'arborescence auditée.

La décision d'architecture est désormais confirmée :

```text
SQLite = source de vérité persistante
snapshot = configuration Last Known Good read-only
Discord = réalité opérationnelle temporaire des rôles membres en recovery
```

## Contraintes déjà retenues

Le snapshot devra être :

- versionné ;
- écrit atomiquement ;
- mis à jour uniquement après un état cohérent ;
- lisible sans SQLite ;
- strictement secondaire ;
- insuffisant, seul, pour autoriser une nouvelle mutation persistante de
  configuration ;
- suffisamment complet pour permettre aux questionnaires déjà configurés de
  continuer à fonctionner.

### Décision complémentaire — 21 septembre 2026

Le terme « read-only » concerne le **snapshot et la configuration persistée**,
pas l'ensemble du service Discord.

En mode `RECOVERY / SNAPSHOT` :

```text
questionnaire existant
→ lecture du Last Known Good
→ planning / preflight
→ mutation des rôles membre sur Discord autorisée

mutation structurelle/configuration
→ interdite
```

Le but du snapshot est précisément de maintenir l'attribution autonome des
accès membres pendant que SQLite est diagnostiquée.

Pour les rôles membres gérés par Claviger, Discord devient temporairement
l'état opérationnel faisant foi pendant la fenêtre de recovery. Une future
réconciliation devra comparer cet état à la persistence lorsque SQLite redevient
saine.

Un journal hors SQLite n'est envisagé qu'en **fallback exceptionnel** si
Claviger se trouve simultanément en snapshot et incapable de confirmer une
mutation Discord. Ce journal devra rester minimal, atomique et limité aux
membres/opérations en anomalie.

## Question principale

Que doit contenir le **Last Known Good** ?

Il faudra éviter deux extrêmes :

### Trop pauvre

```text
schema_version
timestamp
```

→ inutile pour diagnostiquer/reconstruire.

### Copie complète sauvage de SQLite

→ deuxième source de vérité déguisée.

### Priorité

**P0 — conception puis implémentation après fermeture des risques immédiats DB/mutation partielle.**

---

# 20. Backup opérationnel

## État actuel

❌ Aucun workflow runtime audité ne fournit encore de backup SQLite avant
migration, déploiement ou selon une planification nocturne.

Ce besoin reste distinct du snapshot applicatif.

## Décision retenue

Le hardening V1.1 doit fournir un **moteur de sauvegarde SQLite fiable et
réutilisable**.

Politique nocturne cible :

```text
23 h
→ produire une sauvegarde SQLite cohérente
→ contrôler qu'elle est lisible / valide
→ confirmer sa copie sur le NAS
→ conserver les deux sauvegardes validées les plus récentes
→ supprimer l'ancienne seulement après succès complet
```

Exemple de rotation :

```text
avant 23 h : J-2 + J-1
après succès : J-1 + J
```

Si la création, la validation ou la copie NAS échoue :

```text
J-2 + J-1 restent conservées
```

Il n'est pas utile d'accumuler des dizaines de versions d'une DB qui peut rester
stable plusieurs jours.

Le même moteur doit servir aux backups **pré-migration** et **pré-déploiement**.
Ces sauvegardes ponctuelles restent obligatoires ; leur interaction exacte avec
la rotation nocturne sera fixée pendant l'implémentation.

Le stockage durable cible est un dossier dédié sur le NAS. L'intégration Linux /
Docker devra garantir qu'un backup annoncé comme réussi est réellement présent
et validé avant toute rotation destructive.

### Priorité

**P0 avant production.**

---

# 21. Matrice actuelle de robustesse

| Scénario | État actuel | Audit |
|---|---|---|
| DB absente au startup | maintenance, pas de création automatique | ✅ |
| DB absente + initialize manuel | autorisé pour première install | 🟡 distinction recovery absente |
| DB inaccessible au startup | `UNAVAILABLE`, maintenance | ✅ |
| DB tombe pendant runtime | erreurs repository par opération | 🟡 |
| DB trop récente | refus | ✅ |
| DB ancienne | migration explicite | ✅ |
| migration échoue | rollback de la migration courante | ✅ |
| corruption SQLite partielle | `quick_check` + état `INTEGRITY_FAILED` | ✅ |
| ownership absent | recovery bind | ✅ |
| ownership incorrect | startup fail-closed | ✅ / 📌 UX |
| catégorie ADMIN supprimée | recovery détecté live | ✅ |
| salon ADMIN supprimé | recovery détecté live | ✅ |
| permissions ADMIN cassées | recovery détecté live | ✅ |
| rôle catalogue supprimé | invalidé par resync | ✅ |
| salon catalogue supprimé | target invalidée | ✅ |
| mapping catalogue ambigu | target non exploitable | ✅ |
| rôle catalogue non manageable | target non exploitable | ✅ |
| rôle principal supprimé | preflight refuse | ✅ |
| rôle principal non manageable | preflight refuse | ✅ |
| rôle IA supprimé — owner | preflight refuse lors activation | ✅ |
| rôle IA supprimé — consumer | peut tomber implicitement en no-IA | 🟡 |
| formulaire stale | soumission refusée | ✅ |
| ressource supprimée après ouverture | rebuild/preflight protègent | ✅ |
| échec avant première mutation | aucun effet de bord | ✅ |
| échec après mutation partielle | erreur dédiée avec IDs | 🟡 |
| rollback mutation partielle | absent | 📌 |
| reporting forum supprimé | logger, fallback DM pas garanti | 🟡 |
| restart normal | lifecycle dédié testé | ✅ |
| restart pendant mutations | pas de journal/recovery dédié | 🟡 |
| guild unavailable | runtime local invalidé | ✅ |
| guild available | runtime reconstruit | ✅ |
| isolation multi-guild automatisée | couverte | ✅ |
| isolation multi-guild réelle | à smoke | 🔬 |
| snapshot Last Known Good | absent | ❌ |
| backup opérationnel | absent | ❌ |

---

# 22. Ordre de travail recommandé après cet audit

L'ordre ci-dessous est une proposition de séquençage, pas encore une décision d'implémentation.

## Tranche H1 — sécurité DB et mode minimal

Avancement :

- ✅ **H1.1** — distinguer disponibilité et intégrité avec `PRAGMA quick_check`
  et l'état `INTEGRITY_FAILED`.

Objectif restant :

- intégrer cette distinction au contrat runtime minimal ;
- définir le comportement face à une DB suspecte/corrompue ;
- distinguer première installation et DB attendue disparue ;
- introduire le contrat runtime normal / minimal / hard stop ;
- conserver le fail-closed ;
- appliquer ce contrat à l'ownership mismatch sans aucun rebind automatique.

Gate :

- tests DB ciblés ;
- aucune création automatique inattendue ;
- DB trop récente toujours strictement read-only côté recovery.

---

## Tranche H2 — mutations partielles

Objectif :

- tester réellement `WorkflowRoleExecutionPartialError` ;
- enrichir son reporting ;
- décider rollback vs réconciliation ;
- couvrir interruption/restart au milieu d'une exécution.

Gate :

- scénario première mutation OK / deuxième KO ;
- résultat exact observable ;
- aucun mensonge « succès » côté utilisateur ;
- report admin exploitable.

---

## Tranche H3 — drift live restant

Objectif :

- rôle IA global disparu ;
- fallback reporting quand ADMIN persisté est complet mais cassé dans Discord ;
- vérifier les autres ressources live importantes.

Gate :

- fail-closed ;
- recovery humain identifiable ;
- aucune dégradation silencieuse en état métier différent.

---

### Décision de recovery manuel sur drift

Pour les ressources Discord structurantes référencées par ID, Claviger ne doit
pas tenter de réparer automatiquement une divergence en recherchant un rôle ou
un salon au nom similaire.

Le comportement attendu est :

```text
drift détecté
→ fail-closed
→ report avec l'ID attendu et l'état live observé
→ action explicite de l'admin
```

Une future IA pourra proposer une correspondance ou une procédure de réparation,
mais aucune mutation ne doit être exécutée sans validation explicite de l'admin.

---

## Tranche H4 — snapshot Last Known Good et backups

Objectif :

- format snapshot versionné ;
- écriture atomique ;
- politique de mise à jour ;
- lecture recovery sans DB ;
- preuve qu'il ne devient pas source de vérité ;
- moteur de backup SQLite cohérent ;
- rotation nocturne de deux sauvegardes à 23 h ;
- stockage NAS ;
- backup explicite pré-migration / pré-déploiement.

Gate :

- snapshot corrompu/non lisible géré ;
- snapshot d'une autre version reconnu ;
- aucune mutation de configuration persistante autorisée sur snapshot seul ;
- questionnaires existants encore utilisables avec mutation des rôles membres
  lorsque Discord est sain ;
- fenêtre recovery identifiable pour la future réconciliation membre ;
- fallback hors SQLite prévu uniquement pour une double panne
  snapshot + mutation Discord ;
- multi-guild correctement représenté.

---

## Tranche H5 — matrice de panne et smoke multi-guild

Objectif :

- exécuter les scénarios réels de la matrice ;
- casser volontairement Guild A ;
- confirmer Guild B intacte ;
- tester restart / return / drift.

Cette tranche doit alimenter l'audit final V1.1.

---

# 23. Tests existants particulièrement utiles pour cette tranche

Liste non exhaustive des suites déjà directement pertinentes :

```text
tests/database/test_database_connection.py
tests/database/test_database_status.py
tests/database/test_database_schema_lifecycle.py
tests/database/test_database_schema_migrations.py

tests/services/runtime/test_database_ownership_service.py
tests/services/runtime/test_guild_configuration_readiness_service.py

tests/services/admin/test_admin_configuration_reconciliation_service.py
tests/services/admin/test_admin_configuration_inspection.py

tests/services/catalogs/test_role_channel_discovery.py
tests/services/catalogs/test_catalog_entry_synchronization_service.py

tests/services/workflows/test_workflow_configuration_reconciliation_service.py
tests/services/workflows/test_workflow_questionnaire_coordinator_service.py
tests/services/workflows/test_workflow_role_planner_service.py
tests/services/workflows/test_workflow_role_executor_service.py

tests/runtime/test_bot.py
tests/runtime/test_bot_multi_guild_lifecycle.py
tests/runtime/test_restart_completion_lifecycle.py

tests/reporting/test_report_service_unavailable.py
```

---

# 24. Règles à préserver pendant le hardening

Les correctifs à venir ne doivent pas affaiblir les acquis suivants :

1. **fail closed** en cas d'ambiguïté ;
2. aucune mutation Discord avant preflight complet lorsque le plan est connu ;
3. SQLite reste la source de vérité ;
4. le snapshot/configuration reste read-only côté recovery, tandis que les
   mutations de rôles membres nécessaires aux questionnaires peuvent rester
   autorisées si Discord est sain ;
5. aucune réparation destructive automatique d'une DB absente ou incorrecte ;
6. aucune contamination inter-guild ;
7. ADMIN recovery reste accessible même si le routing normal est cassé ;
8. reporting ne doit pas casser l'opération métier qu'il observe ;
9. les rôles hors périmètre d'un workflow restent intacts ;
10. les couches restent séparées :
   - persistence ;
   - discovery ;
   - planning ;
   - preflight ;
   - execution ;
   - reporting ;
   - recovery.

---

# 25. Conclusion de l'audit initial

La V1.1 n'a pas besoin d'une réécriture de robustesse.

Le socle déjà construit possède les protections structurantes nécessaires pour aborder le hardening par petites tranches ciblées.

Les risques les plus importants à fermer avant Succumbrae sont :

```text
1. intégrité / perte de DB
2. mutation Discord partielle
3. drift du rôle IA global
4. reporting ADMIN cassé malgré config persistée complète
5. snapshot Last Known Good
6. backup opérationnel de déploiement
```

L'inventaire a été lu et accepté comme base de travail le 19 septembre 2026.

La prochaine implémentation prévue est la **tranche H1 — sécurité DB et mode
minimal**, en conservant les décisions de snapshot et de backup ci-dessus comme
contrats de la branche.
