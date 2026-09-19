# ROADMAP — reste à faire pour Claviger V1.1

## Checkpoint de reprise — 19 septembre 2026

**Feature active :** `feature/v11-hardening-recovery`  
**Base fonctionnelle intégrée dans `develop` :** `6ba15319901932945c3ae66ad3313121f746ac6e`  
**Schéma SQLite courant :** V12  
**Audit hardening :** `08_AUDIT_HARDENING_RECOVERY_V1_1_2026-09-19.md`

Les branches de refactor/workflow précédentes sont désormais incluses dans
`develop`. La branche active de hardening est issue de ce `develop` à jour.

Le code du HEAD reste la source de vérité.

---

# 1. Tranches terminées — ne pas refaire

## Runtime multi-guild

Validé :

- état runtime par `guild_id` ;
- lifecycle Discord event-driven ;
- isolation de readiness ;
- locks par guild ;
- join / available / unavailable / remove indépendants ;
- synchronisation de command tree par guild.

## Identité, ownership et ADMIN

Validé :

- identité application séparée de la guild ;
- ownership SQLite lié à l'application Discord ;
- mismatch fail-closed ;
- une base applicative pour plusieurs guilds ;
- discovery / reconciliation / provisioning ADMIN ;
- reporting activity/error par guild ;
- fallback incident avant disponibilité d'ADMIN ;
- commandes normales restreintes au salon ADMIN.

## Migration V11 / V12

Validé :

- migration des anciens catalogues spécialisés vers
  `guild_catalog_entries` / `guild_catalog_entry_targets` ;
- IA globale déplacée dans `guild_settings` ;
- anciennes colonnes V1 retirées ;
- contexte historique `ai_preference` retiré ;
- schéma V12 avec `guild_ai_questionnaire_owner` ;
- owner unique par guild avec FK vers `guild_workflows`.

## Configuration IA globale

Validé en smoke réel :

```text
ADMIN
→ IA globale
→ rôle IA
→ workflows
```

Le rôle IA est guild-scoped et n'appartient pas à un workflow.

## Configuration générique des workflows

Validé :

- sélection ou création de catégorie ;
- salon de gestion ;
- salon d'exécution ;
- rôle principal ;
- préfixe questionnaire ;
- confirmation avant première mutation ;
- persistence SQLite après provisioning ;
- rôle principal jamais choisi parmi les rôles réservés ;
- revalidation backend des réservations ;
- structures Discord déjà utilisées annotées et réutilisables.

Les réservations excluent notamment :

- rôle de l'application / rôles d'intégration ;
- rôle IA global ;
- rôles principaux déjà utilisés ;
- rôles appartenant à des patterns/catalogues déjà liés ;
- rôles techniquement non manipulables.

## Ownership de la question IA

Validé :

- un seul workflow par guild peut poser/modifier la préférence IA ;
- l'owner est persistant ;
- l'ownership peut être déplacé ;
- les autres workflows ne modifient jamais le rôle IA global.

Convention fonctionnelle actuelle :

```text
premier questionnaire obligatoire (/membre)
→ propriétaire de la question IA

autres questionnaires
→ consommateurs de l'état IA global
```

## Runtime questionnaire générique

Implémenté :

```text
workflow persisté
→ commande dynamique au restart
→ synchro catalogue Discord
→ lecture état membre
→ lecture IA globale
→ questionnaire générique
→ soumission complète
→ rebuild frais
→ planning pur
→ preflight complet
→ mutations Discord
→ reporting
```

Le moteur ne contient pas de branche métier dédiée à Membre ou Adult.

Variantes supportées :

- `base` ;
- paire `no_ai` / `ai` ;
- `ai` seule ;
- `no_ai` seule.

Contrat fonctionnel confirmé pendant le smoke Laboratorium :

```text
Sans IA
→ base
→ no_ai

Avec IA
→ base
→ no_ai
→ ai en supplément
```

Une paire sélectionnée produit donc `no_ai` sans IA puis `no_ai + ai` avec
IA. Une entrée `no_ai` seule reste disponible dans les deux états ; une entrée
`ai` seule n'est disponible qu'avec IA. La préférence IA est additive et ne
doit jamais supprimer le socle `no_ai`.

### UX questionnaire et pagination

Pour la V1.1, un questionnaire utilise une seule modal tant que son volume reste
raisonnable. Le scroll Discord suffit pour les petits et moyens catalogues et
évite d'ajouter une mécanique de navigation pendant la fermeture de la V1.1.

La **V1.3** devra introduire une pagination / navigation multi-étapes pour les
gros catalogues. La raison est UX autant que technique : éviter une modal trop
longue, rester sous les limites des composants Discord et rendre les choix plus
faciles à parcourir. Les pages ne constituent pas des transactions séparées :
elles accumulent un état temporaire, puis un seul planning, un seul preflight et
une seule exécution ont lieu après la validation finale.

## Diagnostics administratifs — tranche terminée

Les trois diagnostics sont maintenant considérés comme validés.

### `config scan`

Affiche :

- DB / ownership ;
- ADMIN ;
- IA globale ;
- compteurs déclaratifs ;
- workflows configurés ;
- catégorie et commande ;
- structures Discord **potentielles** détectées par la discovery ;
- composition protégée / interactive ;
- workflows déjà liés à ces structures.

Le rendu Discord ne montre plus les IDs techniques et n'expose plus la policy
legacy comme configuration active.

### `roles scan`

Affiche :

- rôle de l'application ;
- rôle IA ;
- rôles principaux ;
- rôles catalogue configurés ;
- rôles manipulables hors workflow ;
- rôles non manipulables ;
- anomalies de pattern.

Smoke Laboratorium accepté.

### `catalog scan`

Affiche séparément pour chaque workflow :

- état de structure ;
- état de commande ;
- catégorie ;
- salon de gestion ;
- salons d'exécution ;
- rôle principal ;
- salons explicitement visibles par ce rôle ;
- ownership de la question IA ;
- état du catalogue ;
- pattern ;
- métadonnées ;
- synchro BDD ;
- anomalies de mapping/manageability.

Les problèmes sont mis en avant avant le résumé chiffré.

---

# 2. Tranche terminée — administration des métadonnées catalogue

## Constat réel sur Laboratorium

Le diagnostic actuel a permis d'identifier précisément le cas suivant :

```text
Workflow Membre
→ catalogue interest-
→ interest-test présent
→ target BDD présente
→ label manquant
→ description manquante
```

Le workflow Adult possède déjà des métadonnées complètes sur ses entrées utiles.

Le besoin n'est donc plus théorique : il faut une surface d'administration pour
corriger proprement les entrées incomplètes.

## Cible

Réintroduire l'utilité des anciens `catalog sync` / `catalog next`, mais
uniquement comme façade du backend générique V1.1.

Le backend de référence reste :

```text
RoleChannelDiscoveryService
→ CatalogEntrySynchronizationService
→ CatalogEntryRepository
```

Aucune seconde implémentation de synchronisation ne doit être créée.

## Fonctionnalités attendues

1. **Synchronisation volontaire**
   - déclencher le scan Discord ;
   - créer/rafraîchir les targets techniques ;
   - préserver les métadonnées humaines existantes ;
   - signaler les mappings invalides ou ambigus.

2. **Configuration des métadonnées**
   - trouver la prochaine entrée incomplète ;
   - afficher sa clé logique et ses rôles/targets ;
   - saisir au minimum `label` et `description` ;
   - emoji facultatif ;
   - enregistrer sans modifier les targets Discord.

3. **Boucle d'administration**
   - après sauvegarde, proposer/afficher l'entrée suivante ;
   - quand tout est complet, signaler clairement que le catalogue est prêt.

4. **Diagnostic**
   - `catalog scan` doit passer immédiatement de
     `MÉTADONNÉES INCOMPLÈTES` à `READY` lorsque la dernière entrée requise
     est complétée.

## Contrat

Une entrée est prête pour le questionnaire lorsque :

```text
enabled
AND label non vide
AND description non vide
AND au moins une target exploitable pour le contexte
```

L'emoji reste facultatif.

## Gate de sortie — validée sur Laboratorium

Le smoke `catalog scan → catalog sync → catalog next → catalog scan` a validé
la synchronisation technique et la complétion des métadonnées. Les anomalies
volontaires du catalogue Adult restent visibles comme prévu.

- Ruff vert ;
- tests ciblés verts ;
- pytest complet vert ;
- metadata existantes préservées après sync ;
- entrée incomplète complétable depuis Discord ;
- aucune target technique modifiée par la saisie metadata ;
- `catalog scan` reflète immédiatement le nouvel état ;
- smoke réel sur `interest-test`.

---

# 3. Smoke questionnaire — Laboratorium

Après la tranche metadata :

## Préconditions attendues

```text
Workflow Membre
- commande /membre
- rôle principal Membre
- catalogue interest-
- owner de la question IA
- interest-test metadata complète

Workflow Adult
- commande /adult
- rôle principal adult
- catalogue access-
- non propriétaire de la question IA
```

Le rôle IA global actuel est `option-ia`.

## Matrice Adult déjà préparée

Le laboratoire contient volontairement :

- une target `base` ;
- une paire `ai` / `no_ai` ;
- une target `ai` seule ;
- une target `no_ai` seule ;
- un rôle catalogue non manipulable ;
- un rôle manipulable hors workflow servant de témoin d'isolation.

## Parcours à valider

### A. Membre avec IA

```text
/membre
→ accepter la préférence IA
→ reçoit option-ia
→ sélection interest-test
→ reçoit Membre + interest-test
```

Puis :

```text
/adult
→ aucune question IA
→ lit option-ia
→ propose/résout les variantes IA
→ attribue les targets IA appropriées
→ conserve interest-test et les rôles hors périmètre
```

### B. Membre sans IA

```text
/membre
→ refuser IA
→ option-ia absente
→ /adult
→ variantes no_ai utilisées
```

### C. Bascule

```text
/membre
→ changer préférence IA
→ /adult
→ sélection logique conservée
→ target concrète opposée retirée
→ nouvelle target appropriée ajoutée
```

### D. Cas de sécurité

- rôle non manipulable : aucun effet de bord partiel avant preflight ;
- formulaire devenu stale : refus ;
- rôle/salon disparu après ouverture : refus fail-closed ;
- commande Adult hors salon d'exécution : refus ;
- rôle extérieur au workflow : préservé.

---

# 4. Smoke questionnaire — seconde guild

Rejouer la même logique sur une autre guild avec une configuration différente.

Objectifs :

- aucune contamination inter-guild ;
- commandes dynamiques propres à chaque guild ;
- IA globale propre à chaque guild ;
- owner questionnaire propre à chaque guild ;
- catalogues/patterns indépendants ;
- reporting dans les destinations de la guild concernée.

Si la seconde guild ne possède pas encore les structures métier nécessaires,
les créer à partir des résultats de `config scan` et `catalog scan` avant le
questionnaire.

---

# 5. Robustesse / recovery / snapshots

**Tranche active :** `feature/v11-hardening-recovery`.

L'audit initial est terminé et sert de matrice de travail :

`08_AUDIT_HARDENING_RECOVERY_V1_1_2026-09-19.md`

Après validation fonctionnelle :

- rôle ou salon supprimé ;
- permission du bot retirée ;
- rôle devenu non manipulable ;
- mapping devenu ambigu ;
- restart pendant/après une opération ;
- mutation Discord partiellement réussie ;
- guild unavailable puis available ;
- DB absente ;
- DB indisponible ;
- DB corrompue ;
- DB trop récente ;
- ownership incorrect ;
- isolation stricte multi-guild.

## Last Known Good / snapshots

SQLite reste la source de vérité.

Le snapshot doit être :

- versionné ;
- écrit atomiquement ;
- read-only côté recovery ;
- mis à jour uniquement après validation d'un état cohérent ;
- insuffisant à lui seul pour autoriser une mutation persistante si SQLite est
  indisponible.

Séparer :

```text
snapshot applicatif de recovery
≠
backup opérationnel avant migration/déploiement
```

## Mode minimal — décision actée

Claviger doit pouvoir rester vivant en **mode minimal** lorsqu'une panne sérieuse
rend le runtime normal indisponible mais qu'un fonctionnement réduit reste sûr.

Pour V1.1 :

- workflows métier et mutations normales désactivés en mode minimal ;
- diagnostic et recovery conservés lorsqu'ils peuvent fonctionner sans faire
  confiance à l'état défaillant ;
- ownership DB toujours fail-closed ;
- aucun rebind automatique en cas de mismatch.

Cette architecture prépare la V2.0 : à terme, l'IA conversationnelle devra
pouvoir rester accessible en mode minimal uniquement à l'owner et à un rôle de
secours dédié.

## Backups SQLite — décision actée

Le moteur de backup fait partie de cette tranche.

Politique cible :

```text
tous les jours vers 23 h
→ backup SQLite cohérent
→ validation
→ copie NAS confirmée
→ rotation
→ 2 sauvegardes validées conservées
```

La sauvegarde la plus ancienne n'est supprimée qu'après succès complet de la
nouvelle. En cas d'échec, les deux sauvegardes précédentes restent intactes.

Le même mécanisme devra servir aux backups obligatoires pré-migration et
pré-déploiement.

---

# 6. Audit et nettoyage de fermeture

Effectuer une passe dédiée :

- architecture ;
- sécurité ;
- permissions Discord ;
- persistence / migrations ;
- logs / reporting ;
- imports et compatibilités legacy ;
- documentation ;
- cohérence `src/` ↔ `tests/`.

Les anciennes policies spécialisées ne doivent plus être présentées comme la
source de vérité des workflows V1.1.

---

# 7. CI/CD et environnement Linux

## CI

Conserver au minimum :

```text
ruff
pytest
```

sur les branches d'intégration appropriées.

## CD

Le déploiement contrôlé doit partir de :

```text
deploy/succumbrae
```

avec :

- secrets hors dépôt ;
- backup SQLite avant déploiement/migration ;
- Docker/Compose ;
- validation Linux ;
- reporting actif après restart.

Ne pas déployer directement depuis `main`.

---

# 8. Smoke final V1.1 et promotion

Ordre de promotion restant :

```text
feature/v11-hardening-recovery
    ↓
develop
    ↓
deploy/succumbrae
    ↓
Succumbrae réel
    ↓
smoke 100 %
    ↓
main
```

Les anciennes branches `refactor/generic-workflows-v11` et
`feature/v11-ai-config-server` sont déjà incluses dans `develop`.

Aucun merge sans acceptation explicite du développeur.

---

# 9. Ordre strict résumé

```text
1. ✅ Métadonnées catalogue — validées
2. ✅ Smoke questionnaire Laboratorium — validé par le développeur
3. Smoke complémentaire non-admin / seconde guild
4. 🔧 Hardening / recovery / snapshots / backups — branche active
5. Audit final
6. CI/CD + validation Linux
7. Smoke final V1.1
8. Documentation finale
9. Feature hardening → develop
10. Deploy/succumbrae
11. Validation production → main
```

Ne pas partir sur V1.2, Web Admin ou agent IA avant fermeture de ce socle V1.1.
