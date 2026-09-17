# Migration V11 — contrat, intégration et passation

## Périmètre et état de livraison

Base de travail : `Yrekk/claviger-discord-bot`, branche `refactor/generic-workflows-v11`, commit `8353649294221ff009b944c7f168ab090260c0de`.

Cette tranche implémente uniquement le stockage V11 et la conversion historique. Les migrations 1 à 10 sont inchangées. Les fichiers sont livrés pour intégration manuelle ; aucun commit ni push n'a été effectué par l'assistante.

Le choix des workflows génériques répond à la robustesse et à la flexibilité : partager les règles métier entre Discord et une future interface Web, éviter les moteurs spécialisés par questionnaire. Les couches restent UI/contrôleur, DTO, service et repository. L'UI présente les décisions du service.

**Cette tranche ne constitue pas une V1.1 déployable.** L'initialisation de la base applique automatiquement les migrations : ne pas lancer le bot sur une base réelle après ce seul remplacement. Le wizard actuel utilise encore les contextes IA historiques ; tant que ses lectures et écritures ne sont pas adaptées, elles pourraient diverger des nouveaux paramètres. Tester ici avec pytest, qui utilise des bases temporaires. La répétition de migration sur copie des bases réelles vient après l'adaptation de config-server.

## Implémenté dans cette tranche

### Stockage générique

Les tables `guild_member_interests` et `guild_adult_accesses` sont supprimées à la fin de la transaction V11. Elles sont remplacées par :

- `guild_catalog_entries` : choix logique et métadonnées de présentation ;
- `guild_catalog_entry_targets` : cibles rôle/salon, variante `base`, `no_ai` ou `ai`, et états de disponibilité.

Les catalogues configurés avec le préfixe historique exact sont réutilisés. Sinon, un catalogue de migration est créé sans inventer de workflow ni de liaison. Les préfixes historiques personnalisés sont respectés. Les chevauchements de préfixes, les clés ambiguës, les rôles dupliqués et les conflits avec le rôle de préférence IA font échouer la conversion plutôt que de perdre ou réaffecter silencieusement des données.

Les paires IA/No-IA deviennent une entrée avec deux cibles. **No-IA fait foi** pour les métadonnées de l'entrée, même si elles sont vides ; aucun remplacement automatique par les métadonnées IA. Les identifiants, noms, mappings et états de chaque cible sont conservés et comparés à la source. Les singletons conservent leurs propres métadonnées. Aucun emoji par défaut n'est ajouté en base.

`access-special` est un singleton `special` du catalogue `access-`. Un préfixe distinct doit être configuré explicitement, par exemple `accessspecial-` ou `access_special-`. Le classificateur de variantes existant est réutilisé pour la conversion historique.

### Paramètres IA de guild

`guild_settings.ai_enabled` accepte `NULL` (non configuré), `0` (désactivé) et `1` (activé). `ai_role_id` accepte un identifiant positif ou `NULL`.

Un contexte historique `ai_preference` fournit son activation et son rôle déjà enregistré. En l'absence de ce contexte, des cibles IA historiques justifient l'activation sans inventer d'identifiant de rôle : `1 / NULL`. Sans preuve historique IA, le réglage reste non configuré. Une désactivation explicite enregistrée dans le contexte prime sur l'inférence historique.

La migration ne contacte pas Discord : l'existence actuelle et la manipulabilité du rôle seront vérifiées dans le parcours de configuration. Les anciens contextes restent temporairement présents pour l'adaptation suivante ; les deux tables de catalogues spécialisées sont, elles, supprimées.

### Aucune récupération inutile

Pour une base initialisée depuis la version 0, les migrations de structure 1 à 11 sont rejouées, mais les lectures et conversions des données historiques sont entièrement sautées. Les tables anciennes sont créées vides par leurs migrations puis retirées par V11.

Pour une base existante, un `EXISTS` vérifie la présence de lignes avant d'appeler chaque convertisseur. Une source vide n'est pas chargée ni convertie. Les contextes IA sont traités seulement si nécessaire.

Une nouvelle guild utilise la base de l'application déjà migrée : elle ne rejoue aucune migration. « Nouveau serveur » et « nouvelle base » sont donc deux cas différents.

### Atomicité

`DatabaseSchema` possède la transaction : DDL V11, copie, contrôles, suppression des sources et passage du numéro de version. Toute erreur, y compris une annulation, provoque le rollback de cette migration. Les migrations antérieures validées restent acquises. Une erreur après suppression des sources restaure l'état V10 complet ; une nouvelle tentative est possible.

Ne pas exécuter manuellement les seules instructions SQL de `MIGRATIONS[11]` : la conversion Python fait partie intégrante de la migration.

## Décisions validées pour les tranches suivantes

1. Configuration **ADMIN → IA → workflows**. ADMIN fournit les destinations d'activité/erreur. Le réglage IA partagé doit être connu avant de configurer les workflows.
2. IA désactivée pour la guild : aucune option ou cible IA proposée. IA activée : vérifier le rôle réservé ; si absent ou introuvable, demander sa sélection/création avant de poursuivre. Le rôle est une propriété du serveur, pas une définition par workflow.
3. Le consentement IA du membre reste distinct. Un membre sans consentement voit le côté No-IA des paires et pas les singletons IA-only. Avec consentement, les cibles IA deviennent éligibles.
4. Questionnaires : étape paires puis étape singletons ; sauter toute étape vide. Pas de mutation de rôle avant validation finale. L'option IA est exposée sur le questionnaire configuré à cet effet.
5. Le robot `🤖` par défaut pour un singleton IA-only relève de la présentation, sans stockage de ce défaut en base.
6. Exclure le rôle géré du bot et le rôle IA réservé des propositions de rôles métier. Quand un préfixe appartient à un workflow configuré, ses rôles ne sont plus proposés comme rôle principal. C'est une règle métier explicite, pas une déduction. Revalider côté service.
7. `role scan` : aucun ID affiché ; section IA dédiée ; afficher le nom du workflow et ses rôles liés. Commandes et préfixes relèvent plutôt de `config scan`.
8. IA non configurée/désactivée : « Serveur non configuré pour le rôle IA ». Activée sans rôle : « Rôle IA pas encore attribué ». Rôle enregistré mais absent de Discord : signaler qu'il est introuvable. Sinon afficher son nom.
9. Discord et future administration Web passent par les mêmes services et repositories ; l'UI ne prend aucune décision métier.
10. Le chatbot conversationnel est hors périmètre. Le paramètre présent concerne les accès au contenu IA.

## Ordre de reprise

Après intégration et tests locaux de cette tranche : adapter modèles/repository des paramètres IA et config-server, puis les filtres de discovery et les scans. Construire ensuite le runtime générique des catalogues et questionnaires et sa liaison aux workflows persistés. Vérifier les parcours réels, répéter la migration sur sauvegardes de dev/prod et terminer la validation V1.1. Ne pas refaire la réorganisation de dossiers déjà terminée.

## Fichiers à intégrer

12 fichiers : 3 créations et 9 remplacements complets. Aucun nouveau dossier.
Les nombres ci-dessous comptent des modifications logiques, pas des lignes ; chaque remplacement est une seule opération de copie.

| Fichier | Modifications | Action |
|---|---:|---|
| `src/claviger/database/migration_v11.py` | 1 | Créer |
| `src/claviger/database/schema.py` | 4 | Remplacer |
| `tests/database/test_database_schema_v11.py` | 1 | Créer |
| `tests/database/test_database_schema_structure.py` | 3 | Remplacer |
| `tests/database/test_database_schema_constraints.py` | 2 | Remplacer |
| `tests/database/test_database_schema_migrations.py` | 1 | Remplacer |
| `tests/database/test_database_schema_v10.py` | 1 | Remplacer |
| `README.md` | 3 | Remplacer |
| `documentations/V1.1/README.md` | 2 | Remplacer |
| `documentations/V1.1/05_ROADMAP_RESTANT_V1_1.md` | 4 | Remplacer |
| `documentations/development/MODE_OPERATOIRE_COLLABORATION_DEV_IA.md` | 2 | Remplacer |
| `documentations/V1.1/06_Migration_V11_Contrat_et_Passation.md` | 1 | Créer |

Détail des groupes : `schema.py` ajoute la version/registre, le branchement du convertisseur, la distinction nouvelle base/base existante et le rollback étendu. Les tests de structure modifient les tables attendues, les colonnes IA et les structures génériques ; les contraintes remplacent deux scénarios spécialisés. Les tests de migrations actualisent la liste cible ; V10 retire seulement l'assertion obsolète « version courante = 10 ». README principal : checkpoint, prochaine étape, effectif de tests ; index V1.1 : checkpoint et prochaine étape ; roadmap : checkpoint/version, retrait des moteurs historiques, état IA nullable, passation. Mode opératoire : version et complément de collaboration.

### Intégration locale

Depuis la racine du dépôt, vérifier d'abord :

```bash
git branch --show-current
git rev-parse --short HEAD
git status --short
```

Attendu : `refactor/generic-workflows-v11`, `8353649`, aucun changement local à écraser. Si HEAD ou les fichiers ont changé, comparer avant toute copie. Extraire le ZIP dans un dossier temporaire, puis copier les 12 fichiers en conservant leurs chemins relatifs. Ne pas supprimer les autres fichiers du dépôt.

Commandes de création si l'intégration est faite manuellement (Git Bash/Linux) :

```bash
touch src/claviger/database/migration_v11.py
touch tests/database/test_database_schema_v11.py
touch documentations/V1.1/06_Migration_V11_Contrat_et_Passation.md
```

Le ZIP contient déjà les trois fichiers complets ; ces commandes ne sont pas nécessaires si tu copies directement les fichiers extraits.

### Vérifications

Dans l'environnement virtuel du projet, avec les dépendances de développement installées :

```bash
python -m ruff check .
python -m pytest tests/database -q
python -m pytest -q
git diff --check
git diff --stat
git status --short
```

Résultats de préparation locale : Ruff sans erreur ; **104 tests database**, **488 tests au total**, 1 avertissement. Python 3.12.14, discord.py 2.7.1, aiosqlite 0.22.1. Les 44 cas supplémentaires couvrent notamment versions 1 à 10, base neuve sans lectures historiques, sources vides, paires, singletons, préfixes personnalisés, isolation de guilds, conservation des états, conflits, contraintes IA et rollback après suppression des sources.

Aucune validation sur la vraie base du développeur ou de production n'est revendiquée. Les tests temporaires n'autorisent pas encore un déploiement du runtime incomplet.

Après résultats locaux au vert, proposition de commit (à réaliser par le développeur) :

```text
feat: add V11 generic catalog storage and historical migration

Replace legacy member/adult catalog tables with logical entries and targets.
Preserve No-AI metadata, target mappings and guild isolation during migration.
Add nullable guild AI settings and skip recovery for fresh databases.
Cover conversion, constraints and atomic rollback with 44 additional cases.
Document integration limits and the next config-server tranche.
```

Le mode opératoire de collaboration s'applique : aucune publication distante par l'assistante, livraison comptée par fichier, et attente d'une réponse à toute question pédagogique posée avant une nouvelle tranche.
