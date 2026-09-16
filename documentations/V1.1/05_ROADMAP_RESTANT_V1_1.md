# ROADMAP — reste à faire pour Claviger V1.1

État de référence : 16 septembre 2026.

Branche de travail : `refactor/generic-workflows-v11`.

Schéma SQLite courant : **V10**.

Ce document est volontairement autonome. Il doit permettre à une nouvelle session de reprendre la fin de V1.1 sans réinterpréter les anciens prompts, sans refaire le nettoyage architectural déjà terminé et sans introduire de logique métier historique comme nouvelle architecture.

---

## 1. Source de vérité et règles de reprise

Pour toute reprise de développement :

1. lire le `README.md` principal ;
2. lire ce document ;
3. consulter `02_Configuration_Workflows_V1_1.md` pour l'état du wizard/configuration générique ;
4. consulter `03_Arborescence_Cible_Fin_V1_1.md` uniquement comme historique de la réorganisation maintenant terminée ;
5. considérer le code de `refactor/generic-workflows-v11` comme source de vérité si un ancien document diverge ;
6. avancer par petites tranches testées ;
7. ne jamais mélanger un refactor d'arborescence avec une migration fonctionnelle ;
8. ne supprimer une compatibilité fonctionnelle qu'après validation de son remplacement.

Le principe général reste :

```text
comprendre
→ modifier une tranche cohérente
→ tests ciblés
→ Ruff
→ suite complète
→ smoke Discord si nécessaire
→ seulement ensuite poursuivre
```

---

# 2. Déjà terminé — ne pas refaire

## Runtime multi-guild

Déjà en place :

- état runtime par `guild_id` ;
- lifecycle Discord event-driven ;
- isolation de la readiness ;
- isolation des command trees ;
- locks par guild ;
- join / available / unavailable / remove indépendants.

## Identité et ownership

Déjà en place :

- identité application séparée de l'identité locale de guild ;
- ownership SQLite lié à l'application Discord ;
- mismatch fail-closed ;
- aucune base créée par guild.

## ADMIN

Déjà en place :

- discovery ;
- reconciliation ;
- provisioning ;
- persistence SQLite ;
- `/{bot} config-server` ;
- `/{bot} config scan` ;
- reporting activity/error par guild.

## Configuration générique d'un workflow

Déjà implémentée côté configuration :

```text
Discord UI
→ WorkflowConfigurationDraft
→ discovery
→ reconciliation
→ preflight
→ provisioning
→ persistence SQLite
```

Le wizard sait déjà gérer des ressources `existing` ou `create`, construire un résumé et ne muter Discord qu'après confirmation.

**Attention : ceci ne signifie pas que l'exécution runtime des workflows persistés est générique.**

Les façades historiques `/membre` et `/noctis` possèdent encore leurs moteurs d'exécution explicites.

## Réorganisation architecturale de fin de V1.1

Terminée sur la branche de travail :

- arborescence par domaines fonctionnels ;
- chemins canoniques sous `models/`, `repositories/`, `services/`, `ui/` ;
- tests rangés en miroir ;
- mini-README dans les dossiers fonctionnels ;
- suppression des shims plats devenus inutiles ;
- suppression de l'ancien dossier `tests/test_policies/` au profit de `tests/policies/` ;
- suppression du fichier vide parasite `source`.

Ne pas recréer de wrappers de compatibilité uniquement pour restaurer d'anciens chemins d'import.

---

# 3. Prochaine étape obligatoire — Migration SQLite V11

La prochaine tranche fonctionnelle est la **Migration 11**.

Elle ne doit pas être mélangée à une nouvelle réorganisation de dossiers.

## 3.1 Objectif

Faire disparaître du stockage cible les concepts historiques spécialisés quand ils peuvent être représentés par les modèles génériques.

Le runtime cible doit connaître :

- des workflows ;
- des catalogues ;
- des entrées logiques de catalogue ;
- une ou plusieurs cibles Discord par entrée ;
- des rôles et ressources Discord ;
- des paramètres de guild.

Il ne doit pas dépendre architecturalement de notions telles que :

```text
member_interests
adult_accesses
access-ia-*
access-no-ia-*
```

Ces notions peuvent être utilisées **uniquement comme données historiques de migration**.

## 3.2 Paramètres IA au niveau guild

La V11 doit préparer un réglage IA partagé au niveau de la guild :

```text
guild_settings.ai_enabled

guild_settings.ai_role_id
```

Contraintes :

- `ai_enabled` stocké comme booléen SQLite contrôlé (`0/1`) ;
- `ai_role_id` nullable ;
- l'identité durable du rôle IA est son ID Discord ;
- la configuration d'un workflow ne doit plus créer une vérité IA parallèle par workflow.

Le modèle actuel basé sur le contexte `ai_preference` reste une compatibilité à migrer, pas la cible finale.

## 3.3 Catalogue générique

Introduire un modèle séparant :

```text
guild_catalog_entries
→ une option logique du questionnaire

guild_catalog_entry_targets
→ une ou plusieurs cibles Discord pour cette option
```

Une entrée logique porte notamment les métadonnées humaines :

- label ;
- description ;
- emoji ;
- ordre ;
- enabled.

Une cible porte notamment :

- l'identité Discord (`role_id`) ;
- le variant historique migré si nécessaire.

## 3.4 Règle de migration des anciens accès

Exemple historique :

```text
access-ia-test
access-no-ia-test
```

La migration doit produire :

```text
entrée logique : test
├── cible variant ai
└── cible variant no_ai
```

Un ancien accès solo devient :

```text
entrée logique
└── une cible
```

Les anciens noms servent uniquement à calculer le mapping pendant la migration.

Le runtime futur ne doit pas réinterpréter les préfixes de rôles à chaque exécution.

## 3.5 Migration fail-closed et atomique

La migration doit :

1. lire les anciennes tables `guild_member_interests` et `guild_adult_accesses` ;
2. construire les entrées/cibles génériques ;
3. préserver chaque `role_id` source ;
4. détecter doublons et ambiguïtés ;
5. valider le nombre de cibles migrées ;
6. transférer les paramètres IA ;
7. seulement après validation, supprimer les anciennes structures devenues inutiles ;
8. rollback complet en cas d'erreur.

Aucune table historique ne doit être détruite avant validation du résultat cible.

## 3.6 Critère de sortie

La V11 est terminée lorsque :

- une DB V10 représentative migre vers V11 sans perte ;
- les deux anciens catalogues spécialisés sont représentés dans le stockage générique ;
- chaque ancien rôle source est traçable dans une cible générique ;
- les cas ambigus échouent sans mutation partielle ;
- les tests V1→V11 / V10→V11 / schéma neuf V11 sont verts ;
- Ruff et la suite complète sont verts.

---

# 4. Adapter `config-server` au modèle V11

Le wizard de configuration générique existe déjà. Il faut l'adapter au nouveau contrat de persistence et finaliser ses règles génériques.

## Règles attendues

La configuration d'un workflow doit permettre explicitement de choisir ou créer :

- identité fonctionnelle / nom de commande ;
- rôle principal ;
- catégorie ;
- salon de gestion ;
- salon d'exécution ;
- préfixe/catalogue questionnaire ;
- rôle IA partagé de guild lorsqu'il est utilisé.

## Permissions cible

Pour un workflow générique :

```text
salon de gestion
→ @everyone.send_messages = False explicite

salon d'exécution
→ @everyone.send_messages = True explicite

bot
→ view/write nécessaires
```

Le rôle principal du workflow ne doit pas recevoir automatiquement un droit générique d'écriture comme mécanisme de classification.

## Discovery structurelle

Une catégorie candidate de workflow doit posséder au moins :

- un salon texte avec `@everyone.send_messages=False` explicite ;
- un salon texte avec `@everyone.send_messages=True` explicite.

`None` / permission héritée ne compte pas comme preuve structurelle.

## Garde-fou

Aucune mutation Discord ne doit avoir lieu avant la validation finale du draft.

---

# 5. Moteur générique de catalogue et questionnaire

Une fois V11 stabilisée :

- charger les entrées logiques depuis le stockage générique ;
- charger leurs cibles ;
- restaurer les choix utilisateur ;
- valider existence et manageability des rôles ;
- produire une sélection complète ;
- ne muter Discord qu'après validation finale.

Le moteur doit supporter un nombre arbitraire de préfixes/catalogues configurés, sans branches codées en dur pour `member` ou `adult`.

## Parcours adaptatif

Le questionnaire peut rester multi-étapes lorsque nécessaire :

```text
choix principaux
→ choix complémentaires nécessaires ?
   ├── non : validation
   └── oui : étape complémentaire
             → validation
```

Aucune mutation entre les étapes.

---

# 6. Liaison explicite workflow → exécution runtime

Le stockage sait déjà décrire un workflow, mais le runtime ne doit pas deviner quel moteur l'exécute.

Introduire un contrat explicite et déterministe reliant une définition persistée à son executor/handler runtime.

Interdictions :

- pas de dispatch par nom de commande ;
- pas de dispatch par préfixe de rôle ;
- pas de dispatch par nom de workflow ;
- pas de dispatch par nom de salon.

Après cette liaison seulement, la surface de commandes pourra être réellement pilotée par les workflows persistés.

Objectif final :

```text
workflow persisté
→ binding runtime explicite
→ commande générée/persistée
→ moteur générique
```

Les anciennes façades `/membre` et `/noctis` pourront alors devenir des configurations/façades compatibles au lieu d'être des moteurs d'architecture séparés.

---

# 7. Robustesse et recovery

Après stabilisation fonctionnelle :

- vérifier les scénarios de drift ADMIN et workflow ;
- ressources Discord supprimées ;
- permissions modifiées ;
- rôle devenu non gérable ;
- mapping ambigu ;
- DB absente / indisponible / corrompue / trop récente ;
- ownership incorrect ;
- guild unavailable puis available ;
- échec partiel de mutation Discord ;
- reconfiguration d'une guild sans impact sur les autres.

## Last Known Good

Si le mécanisme LKG est conservé pour V1.1, il doit rester :

- read-only en recovery ;
- atomique ;
- versionné ;
- limité aux lectures sûres ;
- jamais utilisé comme seconde base modifiable.

Toute mutation persistante reste fail-closed lorsque SQLite n'est pas exploitable.

---

# 8. Smoke tests Discord DEV

Avant fermeture fonctionnelle V1.1 :

1. guild DEV vierge ;
2. configuration ADMIN depuis `config-server` ;
3. configuration d'un premier workflow sans manipulation SQLite manuelle ;
4. création et réutilisation de ressources ;
5. vérification des permissions management/execution ;
6. cas IA désactivée ;
7. cas IA activée avec rôle partagé ;
8. restart ;
9. exécution du workflow générique ;
10. seconde guild avec configuration différente ;
11. vérifier l'absence de contamination entre guilds ;
12. vérifier reporting activity/error.

---

# 9. Audit de fermeture V1.1

Effectuer une passe dédiée :

- architecture ;
- sécurité ;
- permissions Discord ;
- persistence/migrations ;
- logs et reporting ;
- recovery ;
- documentation ;
- imports et compatibilités résiduelles ;
- cohérence `src/` ↔ `tests/`.

Tout nettoyage résiduel doit être justifié par un remplacement déjà validé.

---

# 10. Documentation finale

Avant intégration :

- mettre le README principal en cohérence avec le comportement réellement smoke-testé ;
- mettre à jour les documents V1.1 devenus historiques ;
- documenter la Migration 11 ;
- documenter le modèle générique de catalogues ;
- documenter le binding runtime ;
- documenter la procédure de migration/déploiement.

---

# 11. Qualité, intégration et déploiement

La CI existe déjà et exécute Ruff + pytest sur `develop` et `main`.

Pour chaque tranche locale :

```bash
python -m ruff check .
python -m pytest -q
```

À la fermeture de V1.1 :

1. obtenir une branche `refactor/generic-workflows-v11` verte ;
2. intégrer proprement dans `develop` ;
3. laisser la CI valider `develop` ;
4. effectuer les smoke tests finaux ;
5. préparer le déploiement contrôlé vers `deploy/succumbrae` ;
6. migrer la DB de déploiement avec sauvegarde préalable ;
7. vérifier démarrage, ownership, migrations et reporting ;
8. seulement ensuite considérer la V1.1 livrable.

---

# 12. Ordre strict résumé

```text
0. Fermer la validation du refactor architectural
1. Migration SQLite V11
2. Adapter config-server au modèle V11
3. Catalogue/questionnaire générique
4. Binding explicite workflow → runtime
5. Robustesse / recovery / éventuel LKG
6. Smoke tests Discord DEV
7. Audit final
8. Documentation finale
9. Ruff + pytest + CI
10. Intégration develop
11. Déploiement contrôlé
```

Ne pas sauter directement à l'étape IA/agentique, à la V1.2 ou à l'administration Web tant que ce socle V1.1 n'est pas fermé.
