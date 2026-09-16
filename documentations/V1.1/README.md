# Documentation V1.1

Ce dossier regroupe les documents spécifiques au développement de Claviger V1.1.

La V1.1 vise notamment :

- le runtime multi-guild ;
- la configuration ADMIN par guild ;
- les workflows configurables ;
- la réduction des dépendances historiques à un serveur unique ;
- la robustesse face aux états partiels ;
- une architecture réutilisable par Discord, une future administration Web et de futurs tools IA.

## État actuel

Le socle multi-guild, la configuration ADMIN, le reporting par guild et la configuration générique d'un workflow jusqu'à sa persistence sont implémentés.

La réorganisation architecturale de fin de V1.1 est également terminée sur `refactor/generic-workflows-v11` : domaines fonctionnels séparés, tests rangés en miroir, mini-README et suppression des anciens shims plats devenus inutiles.

Le schéma SQLite courant reste **V10**. Le prochain chantier fonctionnel est la **Migration V11**, puis le moteur générique de catalogue/questionnaire et la liaison explicite entre workflows persistés et exécution runtime.

## Documents

Les documents numérotés suivent l'évolution du projet :

- `00_Prompt_maitre_continuite_Claviger_V1_1.pdf` : cadrage de continuité historique ;
- `01_Claviger_Retrospective_Interventions_Humaines_V1_1.pdf` : rétrospective des interventions ;
- `02_Configuration_Workflows_V1_1.md` : état du wizard et de la configuration générique des workflows ;
- `03_Arborescence_Cible_Fin_V1_1.md` : cible utilisée pour la réorganisation architecturale ;
- `04_Prompt_Reorganisation_Arborescence_Fin_V1_1.md` : prompt ayant cadré cette réorganisation ;
- `05_ROADMAP_RESTANT_V1_1.md` : **source de reprise prioritaire pour le reste de la V1.1**.

La documentation de continuité décrit l'état d'une période donnée. Le code de la branche de travail reste la source de vérité lorsqu'il a évolué depuis.

Pour reprendre la fin de V1.1 dans une nouvelle session, lire en priorité le README principal puis `05_ROADMAP_RESTANT_V1_1.md`. Ne pas recommencer la réorganisation d'arborescence : elle est considérée terminée.
