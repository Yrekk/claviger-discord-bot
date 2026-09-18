# ROADMAP — reste à faire pour Claviger V1.1

## Checkpoint de reprise — 17 septembre 2026

**Branche feature active :** `feature/v11-ai-config-server`  
**Dernier commit fonctionnel validé avant documentation :** `12c95d51718bed22b9920fcbea69b155f3bccb72`  
**Branche d'intégration cible :** `refactor/generic-workflows-v11`  
**Schéma SQLite courant :** V12  
**`develop` :** ne pas toucher avant fermeture V1.1.

Pour une reprise après coupure de session, lire d'abord :

`07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md`.

Le code réel du HEAD reste la source de vérité.

---

# 1. Déjà terminé — ne pas refaire

## Runtime multi-guild

Validé :

- état runtime par `guild_id` ;
- lifecycle Discord event-driven ;
- isolation de readiness ;
- locks par guild ;
- join / available / unavailable / remove indépendants.

## Identité et ownership

Validé :

- identité application séparée de la guild ;
- ownership SQLite lié à l'application Discord ;
- mismatch fail-closed ;
- une base applicative, plusieurs guilds.

## ADMIN

Déjà en place :

- discovery ;
- reconciliation ;
- provisioning ;
- persistence SQLite ;
- reporting activity/error par guild ;
- `config-server` ;
- scans administratifs, encore à moderniser sur le rendu V11.

## Réorganisation architecturale

Terminée :

- domaines séparés sous `models/`, `repositories/`, `services/`, `ui/` ;
- tests en miroir ;
- mini-README locaux ;
- suppression des anciens shims devenus inutiles.

Ne pas refaire cette réorganisation.

## Migration SQLite V11

**Validée sur playground V10 représentatif.**

La V11 :

- convertit `guild_member_interests` et `guild_adult_accesses` vers les catalogues génériques ;
- prend en charge le cas réel singleton + paire IA/No-IA portant le même suffixe ;
- retire les tables spécialisées après validation ;
- retire les colonnes V1 de `guild_settings` ;
- reconstruit `guild_settings` avec uniquement :

```text
guild_id
ai_enabled
ai_role_id
```

- retire le contexte historique `ai_preference` ;
- remet la décision IA V11 à un état non configuré au lieu d'hériter du workflow historique ;
- reste atomique/fail-closed.

Tests ciblés, Ruff et suite pytest complète : validés localement par le développeur.

## Restart

Le restart n'arrête plus le client avant la fin du callback Discord.

Smoke réel : restart sans erreur.

## Configuration IA globale de guild

Le flux réel est maintenant :

```text
ADMIN
→ IA globale
→ workflows
```

Smoke réel validé sur playground migré : l'étape IA est bien affichée, un rôle IA peut être configuré, puis le wizard continue vers les workflows.

Le rôle IA appartient à la guild, pas à un workflow.

## Ownership du questionnaire IA

La préférence IA utilisateur ne doit être posée que par **un seul workflow par guild**.

Le schéma V12 ajoute :

```text
guild_ai_questionnaire_owner
guild_id PRIMARY KEY
workflow_key FOREIGN KEY → guild_workflows
```

Cette table est l'unique source de vérité pour déterminer quel workflow a le droit de demander/modifier la préférence IA.

Commande prévue et implémentée sur la feature :

```text
/<application> workflow ai-questionnaire
```

Elle permet d'assigner le premier propriétaire puis de déplacer atomiquement l'ownership vers un autre workflow.

Les autres workflows ne posent jamais la question IA ; ils consomment l'état du rôle IA pour choisir leurs variantes `base` / `no_ai` / `ai`.

---

# 2. Prochaine tranche immédiate — réservations de rôles et structures annotées

Le smoke a montré que le sélecteur de rôle principal propose encore des rôles qui ne doivent pas être réutilisés.

Exemples observés :

- rôle du bot ;
- rôle principal d'un workflow existant ;
- rôle sous un préfixe/catalogue déjà lié à un workflow.

## 2.1 Règles de réservation à implémenter

Pour un rôle principal de workflow, exclure :

1. les rôles portés par le compte du bot / rôles d'intégration applicative ;
2. le rôle IA global configuré ;
3. les `primary_role_id` déjà utilisés ;
4. les rôles appartenant aux catalogues/préfixes déjà liés ;
5. les rôles techniquement non manipulables.

Appliquer la règle deux fois :

```text
filtrage UI/discovery
+
revalidation service/preflight
```

L'UI Discord ne doit jamais être l'unique garde-fou d'une règle métier.

## 2.2 Structures déjà utilisées

Plusieurs workflows peuvent partager la même catégorie et les mêmes salons.

Une structure existante ne doit donc pas être bloquée. Elle doit être **annotée** avec les workflows déjà liés.

Exemple :

```text
test-before-member
• protégés : #test-rules
• interactifs : #test-accueil
• workflows déjà configurés : /membre
```

La discovery Discord doit rester structurelle. La corrélation avec SQLite doit être portée par une couche d'enrichissement/coordinator, pas par un repository injecté directement dans `WorkflowStructureDiscoveryService`.

## 2.3 Gate de sortie de cette tranche

- tests ciblés verts ;
- Ruff vert ;
- pytest complet vert ;
- aucun rôle réservé proposé ;
- backend refuse aussi un rôle réservé soumis hors UI ;
- structures partagées visibles et réutilisables ;
- smoke from scratch sur seconde guild.

---

# 3. Smoke from scratch sur seconde guild

Le smoke a déjà validé :

- échec ADMIN sans permission `Manage Channels` ;
- fallback incident en MP tant qu'ADMIN n'existe pas ;
- récupération après ajout des permissions ;
- création des salons/forums ADMIN ;
- passage vers IA globale ;
- chemin IA désactivée ;
- wizard workflow sans choix IA local.

Suite du smoke après migration V11 → V12 :

```text
migrer la BDD DEV vers schéma 12
→ relancer config-server
→ activer IA
→ créer/sélectionner le rôle IA global
→ créer un nouveau workflow
→ /<application> workflow ai-questionnaire
→ choisir ce workflow comme propriétaire
→ relancer la commande et déplacer l'ownership vers un autre workflow
→ vérifier qu'une seule ligne d'ownership existe toujours
```

Puis reprendre le smoke du moteur questionnaire générique lorsqu'il sera construit.

---

# 4. Moderniser les scans

## `role scan`

À adapter au modèle V11 :

- ne plus afficher les IDs dans le rendu humain normal ;
- clarifier ou fusionner visuellement « confiance » et « non manipulable » lorsque les informations se recouvrent ;
- afficher une section IA claire ;
- afficher les rôles principaux de workflows et les rôles/catalogues liés ;
- garder les IDs dans les logs/diagnostics techniques seulement si nécessaires.

## `config scan`

Retirer la présentation `Policy effective — compatibilité actuelle` comme configuration active.

La cible doit diagnostiquer :

```text
ADMIN
→ IA globale
→ workflows
→ catalogues/bindings
```

Les anciens champs `member_role_name`, `adult_role_name`, préfixes et flags spécialisés sont historiques et ne doivent plus être exposés comme source de vérité.

---

# 5. Moteur générique catalogue/questionnaire

Après stabilisation de la configuration :

- charger les entrées logiques depuis `guild_catalog_entries` ;
- charger les targets depuis `guild_catalog_entry_targets` ;
- restaurer les choix utilisateur ;
- adapter les targets aux états IA/no-IA ;
- valider existence et manipulabilité des rôles ;
- ne muter les rôles qu'après validation finale.

Le moteur ne doit pas contenir de branches métier codées en dur pour `member` ou `adult`.

Parcours attendu :

```text
choix principaux
→ étape complémentaire si nécessaire
→ validation finale
→ mutations
```

Aucune mutation entre les étapes.

---

# 6. Binding explicite workflow → runtime

Le stockage sait décrire un workflow, mais le runtime ne doit pas deviner son executor.

Interdictions :

- dispatch par nom de commande ;
- dispatch par nom de workflow ;
- dispatch par préfixe de rôle ;
- dispatch par nom de salon.

Cible :

```text
workflow persisté
→ binding runtime explicite
→ commande/entrée
→ moteur générique
```

---

# 7. Robustesse et recovery

Une fois le runtime générique en place, valider notamment :

- ressources Discord supprimées ;
- permissions modifiées ;
- rôle devenu non manipulable ;
- mapping ambigu ;
- base absente / indisponible / corrompue / trop récente ;
- ownership incorrect ;
- guild unavailable puis available ;
- échec partiel de mutation Discord ;
- isolation entre guilds.

Les snapshots/LKG restent read-only pour le recovery. Ne pas restaurer une seconde persistence modifiable en parallèle de SQLite.

---

# 8. Smoke tests de fermeture V1.1

Avant fermeture :

1. guild DEV/configuration from scratch ;
2. ADMIN ;
3. IA désactivée ;
4. IA activée + rôle partagé ;
5. création et réutilisation de workflow ;
6. structures partagées ;
7. permissions management/execution ;
8. restart ;
9. exécution du runtime générique ;
10. seconde guild avec configuration différente ;
11. isolation inter-guild ;
12. reporting activity/error.

---

# 9. Audit de fermeture

Effectuer une passe dédiée :

- architecture ;
- sécurité ;
- permissions Discord ;
- persistence/migrations ;
- logs/reporting ;
- recovery ;
- documentation ;
- imports/compatibilités résiduelles ;
- cohérence `src/` ↔ `tests/`.

---

# 10. Intégration et déploiement

Quand la V1.1 est réellement fermée :

```text
feature(s) validées
→ refactor/generic-workflows-v11
→ validation complète
→ develop
→ CI
→ smoke final
→ deploy/succumbrae
→ sauvegarde DB
→ migration contrôlée
→ validation runtime/reporting
```

Aucun merge vers la branche d'intégration sans acceptation explicite du développeur.

---

# 11. Ordre strict résumé

```text
1. Réservations/filtrage de rôles + annotation structures
2. Smoke from scratch seconde guild
3. role scan / config scan V11
4. Catalogue/questionnaire générique
5. Binding workflow → runtime
6. Robustesse/recovery
7. Smoke tests de fermeture
8. Audit final
9. Documentation finale
10. Intégration refactor → develop
11. Déploiement contrôlé
```

Ne pas partir sur V1.2, Web Admin ou agent IA avant fermeture de ce socle V1.1.
