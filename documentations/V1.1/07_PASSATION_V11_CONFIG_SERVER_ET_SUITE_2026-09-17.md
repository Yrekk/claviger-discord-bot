# Passation — V11 config-server validé, suite discovery/réservation

**Date :** 17 septembre 2026  
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

## 3. Limites observées pendant le smoke — NON corrigées encore

Le smoke a révélé la prochaine tranche nécessaire. Le sélecteur de rôle principal d'un workflow propose encore des rôles qui devraient être réservés.

Exemples observés :

- rôle du bot (`Experimentum`) proposé ;
- rôle principal d'un workflow déjà configuré (`Membre`) proposé ;
- rôle appartenant à un catalogue/préfixe déjà lié à un workflow (`interest-test`) proposé.

Ce comportement est attendu avec l'implémentation actuelle : `WorkflowStructureDiscoveryService` reprend encore les rôles techniquement manipulables de `RoleDiscoveryService` sans appliquer les réservations métier V11.

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

Ne pas faire ce smoke avant la tranche de filtrage/réservation, afin qu'il valide directement le parcours cible complet.

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

1. implémenter les réservations/filtrages de rôles pour la configuration de workflow ;
2. ajouter la revalidation backend/preflight correspondante ;
3. enrichir les structures détectées avec les workflows déjà liés, sans interdire leur réutilisation ;
4. tests ciblés → Ruff → pytest complet ;
5. smoke from scratch sur la seconde guild ;
6. mettre à jour `role scan` ;
7. mettre à jour `config scan` ;
8. seulement ensuite poursuivre le moteur générique de catalogue/questionnaire et le binding runtime.

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
