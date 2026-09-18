# Passation — V11 config-server validé, suite discovery/réservation

**Date :** 18 septembre 2026  
**Dépôt :** `Yrekk/claviger-discord-bot`  
**Branche de travail :** `feature/v11-ai-config-server`  
**Dernier commit fonctionnel validé avant cette passation :** `12c95d51718bed22b9920fcbea69b155f3bccb72`  
**Branche d'intégration cible :** `refactor/generic-workflows-v11`  
**`develop` :** ne pas toucher avant fermeture V1.1.

Ce document est la passation prioritaire pour reprendre le développement si une session atteint sa limite. Toujours vérifier le HEAD réel de la branche avant de modifier quoi que ce soit.

---

## 1. État réellement validé

### Migration V10 → V11

La migration V11 a été rejouée sur un playground frais issu de la base V10 représentative.

Le contrat final de `guild_settings` est désormais :

```text
guild_settings
├── guild_id
├── ai_enabled
└── ai_role_id
```

Les colonnes spécialisées V1 (`member_role_name`, `adult_role_name`, préfixes, salons historiques, flags spécialisés, etc.) sont retirées du schéma final V11.

Pendant la migration, les anciennes colonnes utiles peuvent encore être lues pour convertir les données historiques, puis `guild_settings` est reconstruit selon le contrat V11.

Pour une guild migrée, la décision IA ne doit pas être héritée de l'ancien workflow :

```text
ai_enabled = NULL
ai_role_id = NULL
```

Le contexte historique `ai_preference` est retiré. La décision IA V11 est donc explicitement reprise par `config-server`.

Les anciens catalogues spécialisés sont convertis vers :

- `guild_catalog_entries` ;
- `guild_catalog_entry_targets`.

Le cas réel où un accès générique et une paire IA/No-IA portent le même suffixe est pris en charge sans perte en conservant deux identités logiques distinctes.

### Tests automatiques

Après alignement des tests historiques sur le contrat V11 :

- tests ciblés : verts ;
- Ruff : vert ;
- suite complète pytest : verte selon validation locale du développeur.

Les anciens tests qui exigeaient encore les colonnes V1 de `guild_settings` ont été corrigés : ces colonnes sont volontairement retirées et ne constituent plus un contrat courant.

### Restart runtime

Le restart Discord ne ferme plus la boucle pendant que `discord.py` termine encore le callback de commande.

Le mécanisme actuel diffère la fermeture jusqu'à la complétion exacte de l'interaction concernée, corrélée par `interaction.token`.

Smoke réel : restart sans erreur console.

### `config-server` et IA globale

Smoke réel concluant sur le playground migré :

```text
ADMIN
→ configuration IA de guild
→ workflows
```

Le bug précédent où la migration faisait considérer l'IA comme déjà configurée est corrigé.

Le développeur a pu :

1. migrer V10 → V11 ;
2. lancer `config-server` ;
3. recevoir l'étape de configuration IA ;
4. choisir/configurer un rôle IA ;
5. continuer vers la configuration des workflows.

Ce smoke valide le contrat de migration et le passage `ADMIN → IA → workflows`.

---

## 2. Architecture IA actuelle

Trois responsabilités restent séparées :

- `GuildAIConfigurationService` : état métier et persistance de la configuration IA ;
- `GuildAIRoleProvisioningService` : effet de bord Discord de création/validation du rôle ;
- `GuildAIConfigurationCoordinatorService` : orchestration des deux et gestion des échecs partiels.

La commande Discord reste une boundary. Le futur Web Admin ou des tools IA devront appeler les mêmes services applicatifs, pas réutiliser une commande Discord comme backend.

Le rôle IA est une propriété globale de guild, pas une propriété de workflow.

---

## 3. Limites observées pendant le smoke — implémentées, validation locale restante

Le smoke a révélé la prochaine tranche nécessaire. Le sélecteur de rôle principal d'un workflow propose encore des rôles qui devraient être réservés.

Exemples observés :

- rôle du bot (`Experimentum`) proposé ;
- rôle principal d'un workflow déjà configuré (`Membre`) proposé ;
- rôle appartenant à un catalogue/préfixe déjà lié à un workflow (`interest-test`) proposé.

Ce comportement a motivé la tranche du 18 septembre. La feature filtre désormais les candidats à partir d'un read-model V11 partagé, tout en conservant `WorkflowStructureDiscoveryService` comme discovery Discord pure. Cette implémentation doit encore passer les tests locaux et le smoke from scratch avant d'être considérée validée.

### Règle cible validée

Pour le choix d'un **rôle principal de workflow**, exclure :

1. tous les rôles portés par le compte du bot / rôles d'intégration applicative ;
2. le rôle IA global configuré ;
3. tout `primary_role_id` déjà utilisé par un workflow ;
4. les rôles appartenant aux préfixes/catalogues déjà liés à des workflows ;
5. tout rôle techniquement non manipulable.

Cette règle doit exister à deux niveaux :

```text
filtrage UI/discovery
+
revalidation backend/preflight
```

Le futur Web Admin ou un tool IA ne doit pas pouvoir contourner une règle seulement parce qu'elle était cachée dans l'UI Discord.

---

## 4. Structures Discord réutilisables

Une catégorie ou un salon peut être partagé par plusieurs workflows.

Donc une structure déjà utilisée ne doit **pas** devenir indisponible.

En revanche, le wizard doit indiquer les bindings existants, par exemple :

```text
test-before-member
• Salons protégés : #test-rules
• Salons interactifs : #test-accueil
• Workflows déjà configurés :
  - /membre
```

Dans le sélecteur, préférer un résumé court :

```text
test-before-member
/membre déjà configuré
```

ou, si plusieurs workflows utilisent la structure :

```text
test-before-member
2 workflows déjà configurés
```

La discovery structurelle doit rester centrée sur Discord. La corrélation avec les workflows persistés doit être faite par une couche d'enrichissement/coordinator dédiée, pas en faisant dépendre `WorkflowStructureDiscoveryService` directement de SQLite.

---

## 5. Scans à mettre à jour après la tranche discovery

### `role scan`

L'affichage courant est encore trop historique.

Décisions validées :

- ne plus afficher les IDs Discord dans le rendu humain normal ;
- revoir le doublon visuel entre « rôles de confiance » et « rôles non manipulables » ;
- ajouter une lecture métier V11 : rôle IA, rôles principaux des workflows, rôles/catalogues liés ;
- conserver les IDs uniquement si nécessaires en diagnostic technique/logs.

### `config scan`

Le bloc `Policy effective — compatibilité actuelle` est obsolète pour la cible V11.

Le scan doit devenir un diagnostic du modèle courant :

```text
ADMIN
→ configuration IA globale
→ workflows configurés
→ catalogues/bindings utiles
```

Les anciennes propriétés spécialisées (`member_role_name`, `adult_role_name`, préfixes historiques, etc.) ne doivent plus être présentées comme configuration active.

---

## 6. Prochain smoke prévu

Le développeur dispose d'un autre serveur adapté à un test **from scratch**, sans rôle IA déjà existant.

Faire ce smoke uniquement après validation locale de la tranche de filtrage/réservation. Il doit alors valider directement le parcours cible complet.

Scénario recommandé :

```text
nouvelle guild
→ ADMIN à configurer
→ IA non configurée
→ activation IA
→ aucun rôle IA existant
→ création ou sélection valide
→ workflow
→ vérifier les rôles proposés
→ vérifier qu'aucun rôle réservé n'est sélectionnable
```

Tester ensuite le cas IA désactivée.

---

## 7. Ordre immédiat de reprise

Ordre recommandé à partir de cette passation :

1. valider localement la tranche actuelle : tests ciblés → Ruff → pytest complet ;
2. corriger les éventuelles régressions sur la feature ;
3. smoke from scratch sur la seconde guild ;
4. mettre à jour `role scan` ;
5. mettre à jour `config scan` ;
6. seulement ensuite poursuivre le moteur générique de catalogue/questionnaire et le binding runtime.

---

## 8. Règles de collaboration à conserver

Pour une modification significative :

```text
branche feature dédiée
→ code/tests/docs par l'assistante
→ pull local du développeur
→ brief pédagogique
→ tests ciblés
→ Ruff
→ pytest complet
→ contrôles Git séparés
→ smoke Discord si nécessaire
→ corrections sur la feature
→ merge seulement après acceptation explicite du développeur
```

L'assistante peut produire, commit et pousser sur la **branche feature** lorsqu'elle a reçu l'autorisation de développer la tranche.

Elle ne merge jamais seule vers `refactor/generic-workflows-v11`, et ne touche pas `develop` avant fermeture V1.1.

Le développeur garde :

- l'arbitrage fonctionnel/architecture ;
- la validation locale ;
- les smoke tests Discord ;
- la décision de merge.

Convention de validation locale : lorsqu'une séquence ordonnée est donnée et que le développeur atteint les dernières commandes sans signaler d'erreur, considérer les étapes précédentes comme exécutées et vertes. Donner `git diff --check` et `git status --short` séparément des tests afin qu'un échec de tests arrête la séquence immédiatement.

---

## 9. Points à ne pas réintroduire

- pas de nouveaux moteurs spécialisés `/membre` / `/noctis` ;
- pas de vérité IA par workflow ;
- pas de dispatch runtime deviné par nom de commande, rôle, préfixe ou salon ;
- pas de logique métier enfermée dans une vue Discord ;
- pas de restauration des colonnes V1 de `guild_settings` ;
- pas de compatibilité legacy conservée uniquement « au cas où » si les snapshots couvrent le recovery ;
- pas de refactor massif d'arborescence : cette réorganisation est déjà terminée.

---

## 10. Fichiers/domaines à relire en premier pour la prochaine tranche

- `src/claviger/services/workflows/workflow_structure_discovery_service.py` ;
- `src/claviger/services/roles/role_discovery.py` ;
- modèles de discovery workflow ;
- repository/configuration des workflows pour connaître `primary_role_id`, catalogues et bindings ;
- service/preflight de configuration workflow ;
- UI de sélection du rôle principal ;
- tests miroir correspondants.

Avant toute modification, vérifier le HEAD réel de `feature/v11-ai-config-server` et comparer avec le commit fonctionnel de référence ci-dessus.

---

## 11. Chaîne de promotion et environnement de déploiement

Cette règle est structurante pour la fermeture V1.1 et remplace toute interprétation où `main` servirait de branche de préproduction.

Chaîne validée :

```text
feature/*
→ PR vers refactor/generic-workflows-v11
→ fermeture V1.1
→ PR vers develop
→ PR/promotion vers deploy/succumbrae
→ déploiement réel sur Succumbrae
→ smoke et validation production
→ seulement si le déploiement est validé à 100 % : promotion vers main
```

La branche distante de déploiement existe sous le nom exact `deploy/succumbrae`.

`main` est la branche **STABLE** : elle ne reçoit que du code déjà validé en production. Le futur CD doit donc partir de `deploy/succumbrae` et non de `main`.

### Environnements

Le projet utilise désormais `CLAVIGER_ENV` pour sélectionner l'environnement. Lors du déploiement V1.1 :

- repartir de la configuration de production existante / `.env.production` ;
- adapter le `.env` servant de sélecteur pour le nouveau conteneur ;
- comparer les variables attendues avec `.env.example` ;
- ne jamais recopier aveuglément le `.env` de développement vers le serveur ;
- valider la configuration Compose avant démarrage ;
- conserver secrets et fichiers d'environnement de production hors Git et hors image Docker.

La mise à jour de l'environnement du serveur fait partie du plan de déploiement V1.1 au même titre que le backup SQLite, la migration et le smoke post-déploiement.


---

## 12. Tranche du 18 septembre — implémentée sur feature, non encore validée localement

**HEAD code au moment de cette mise à jour :** `99cbaa7e7f401ae86d28bc4c2b5ff05a600bbf3e`.

### Contrat IA nettoyé

La configuration d'un workflow ne possède plus de choix IA local :

- retrait de `ai_enabled`, `ai_preference_role` et `ai_preference_role_id` des modèles de configuration workflow ;
- retrait de la création/réconciliation du rôle IA dans le provisioning workflow ;
- retrait de l'écriture/lecture du contexte historique `ai_preference` par `WorkflowConfigurationRepository` ;
- retrait de l'étape IA dans la View workflow.

La source de vérité IA reste donc uniquement la configuration globale V11 de guild portée par `guild_settings`.

### Réservations de rôles

Un nouveau `WorkflowConfigurationInspectionService` combine les workflows persistés et la configuration IA globale pour réserver :

- les `primary_role_id` déjà utilisés par d'autres workflows ;
- le `ai_role_id` global, même s'il est conservé pendant une désactivation ;
- les namespaces de rôles correspondant aux préfixes de catalogues déjà liés.

`RoleDiscoveryService` retire également de ses candidats **tous les rôles portés par le compte du bot**, et plus uniquement son rôle le plus haut.

Le filtrage est appliqué au read-model présenté au frontend, puis revérifié dans le preflight du provisioning immédiatement avant toute mutation Discord.

### Structures déjà utilisées

Les structures détectées restent réutilisables. Elles sont enrichies avec les commandes déjà configurées quand la catégorie, le salon de gestion et un salon d'exécution correspondent au workflow persisté.

L'UI affiche cette information dans le résumé et dans la description du sélecteur.

### Sélecteur de rôle principal

Le `RoleSelect` Discord natif ne permet pas de filtrer arbitrairement les rôles proposés. Il a donc été remplacé pour le rôle principal par un `discord.ui.Select` construit depuis les seuls candidats approuvés par le backend.

Conséquence volontaire V1.1 : Discord limite ce select à 25 options ; la feature présente les 25 premiers candidats approuvés. Une ergonomie plus riche/modal-first reste un sujet V1.3. Le backend reste capable de refuser toute identité réservée même si un autre frontend tente de la soumettre directement.

### Commits de la tranche

- `ecdbcb4c409da4852fa93f0929de109b2c0a9e74` — retrait du contrat IA local aux workflows ;
- `e35d8d20516c7a78419ce4efbb06bc3bfe435ea0` — alignement des tests sur ce contrat ;
- `dcb51527b6c6102f0d2c357f87604fa9c8c74874` — réservations, inspection et annotation des structures ;
- `b468fccd8d223f4b3086d385ec66cb6fb4e36a13` — couverture de non-régression ;
- `99cbaa7e7f401ae86d28bc4c2b5ff05a600bbf3e` — rendu Discord limité aux rôles réellement approuvés.

**Statut :** implémenté et poussé, mais pas encore validé par les tests locaux du développeur ni par le smoke Discord from scratch.
