# Documentation V1.1 — index de reprise

Ce dossier contient les documents de continuité fonctionnelle et architecturale de Claviger V1.1.

## Reprise prioritaire

Pour reprendre le projet après une coupure de session, lire d'abord :

1. `07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md` ;
2. `05_ROADMAP_RESTANT_V1_1.md` ;
3. le HEAD réel de la branche feature indiquée dans la passation.

Le code courant et les décisions les plus récentes priment sur les documents historiques.

## État actuel

Au checkpoint du 17 septembre 2026 :

- schéma SQLite V11 ;
- migration V10 → V11 validée sur playground représentatif ;
- `guild_settings` final limité à `guild_id`, `ai_enabled`, `ai_role_id` ;
- ancien contexte `ai_preference` retiré ;
- restart Discord corrigé et smoké ;
- flux `config-server` validé jusqu'à `ADMIN → IA → workflows` ;
- configuration du rôle IA global validée ;
- prochaine tranche : réservations/filtrage des rôles workflow + annotation des structures déjà utilisées.

## Documents

- `00_Prompt_maitre_continuite_Claviger_V1_1.pdf` : cadrage historique de continuité ;
- `01_Claviger_Retrospective_Interventions_Humaines_V1_1.pdf` : rétrospective ;
- `02_Configuration_Workflows_V1_1.md` : architecture du wizard générique ;
- `03_Arborescence_Cible_Fin_V1_1.md` : cible de réorganisation déjà réalisée ;
- `04_Prompt_Reorganisation_Arborescence_Fin_V1_1.md` : historique de la réorganisation ;
- `05_ROADMAP_RESTANT_V1_1.md` : roadmap actuelle ;
- `06_Migration_V11_Contrat_et_Passation.md` : contrat initial de la tranche migration V11 ;
- `07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md` : **passation opérationnelle courante**.

La branche d'intégration V1.1 reste `refactor/generic-workflows-v11`. `develop` ne doit pas être touchée avant fermeture et validation explicite de la V1.1.
