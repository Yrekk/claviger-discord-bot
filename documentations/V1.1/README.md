# Documentation V1.1 — index de reprise

Ce dossier contient les documents de continuité fonctionnelle et architecturale de Claviger V1.1.

## Reprise prioritaire

Pour reprendre le projet après une coupure de session, lire d'abord :

1. `09_SUIVI_HARDENING_RECOVERY_V1_1.md` — **état opérationnel courant** ;
2. `08_AUDIT_HARDENING_RECOVERY_V1_1_2026-09-19.md` — audit/contrats ;
3. `05_ROADMAP_RESTANT_V1_1.md` — ordre global de fermeture ;
4. `07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md` pour l'historique
   de la tranche précédente ;
5. le HEAD réel de `feature/v11-hardening-recovery`.

Le code courant et les décisions les plus récentes priment sur les documents historiques.

## État actuel

Au checkpoint du 19 septembre 2026 :

- schéma SQLite V12 ;
- runtime multi-guild et workflows génériques intégrés dans `develop` ;
- configuration ADMIN / IA / workflows génériques validée ;
- catalogues génériques et variantes `base` / `no_ai` / `ai` validés ;
- questionnaire générique smoké sur Laboratorium ;
- contrat IA confirmé comme **additif** : `no_ai` reste le socle, `ai`
  s'ajoute lorsque l'IA est activée ;
- branche active : `feature/v11-hardening-recovery` ;
- audit initial hardening/recovery terminé ;
- **H1.1 — disponibilité ≠ intégrité : ✅ VALIDÉ** ;
- **H1.2 — runtime normal / recovery / minimal : ✅ VALIDÉ** ;
- **H1 — sécurité DB et mode minimal : ✅ FERMÉ** ;
- **H2 — mutations Discord partielles : ✅ VALIDÉ** ;
- **H3 — drift live restant : 🧪 À VALIDER** ;
- prochaine étape : validation locale H3, puis H4 — Last Known Good + backups.

Décisions de continuité déjà actées :

- SQLite reste la source de vérité ;
- le snapshot Last Known Good sert de fallback/recovery ;
- en recovery snapshot, les questionnaires restent disponibles et peuvent
  modifier les rôles membres sur Discord ;
- en recovery snapshot, les mutations structurelles/configuration restent
  refusées ;
- la V1.3 doit faire passer les opérations structurelles officielles par
  Claviger afin que le mode runtime puisse réellement jouer son rôle de garde-fou ;
- le mode minimal doit garder Claviger partiellement opérationnel lorsqu'il
  reste possible de le faire en sécurité ;
- en V2.0, l'IA conversationnelle minimale sera limitée à l'owner et à un rôle
  de secours dédié ;
- backup SQLite automatisé vers le NAS vers 23 h ;
- rotation de **deux sauvegardes validées** seulement ;
- suppression de l'ancienne uniquement après création, validation et copie
  réussies de la nouvelle ;
- backup obligatoire avant migration et déploiement ;
- un moteur post-V1.1 de résilience/réconciliation des rôles membres est prévu,
  sans numéro de version fixé à ce stade ; son cadrage est dans
  `documentations/development/RESILIENCE_ETAT_ROLES_MEMBRES_POST_V1_1.md`.

## Documents

- `00_Prompt_maitre_continuite_Claviger_V1_1.pdf` : cadrage historique de continuité ;
- `01_Claviger_Retrospective_Interventions_Humaines_V1_1.pdf` : rétrospective ;
- `02_Configuration_Workflows_V1_1.md` : architecture du wizard générique ;
- `03_Arborescence_Cible_Fin_V1_1.md` : cible de réorganisation déjà réalisée ;
- `04_Prompt_Reorganisation_Arborescence_Fin_V1_1.md` : historique de la réorganisation ;
- `05_ROADMAP_RESTANT_V1_1.md` : roadmap actuelle ;
- `06_Migration_V11_Contrat_et_Passation.md` : contrat initial de la tranche migration V11 ;
- `07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md` : passation de la tranche configuration/workflows ;
- `08_AUDIT_HARDENING_RECOVERY_V1_1_2026-09-19.md` : audit et contrats de hardening ;
- `09_SUIVI_HARDENING_RECOVERY_V1_1.md` : **journal opérationnel courant et point de reprise inter-session**.

Les branches de configuration/workflows précédentes ont été intégrées dans
`develop`. La branche active est `feature/v11-hardening-recovery`, créée
depuis le `develop` à jour.
