# Documentation V1.1

## Livraison stockage V11 — 17 septembre 2026

Tranche préparée depuis `refactor/generic-workflows-v11`, commit `8353649`.
Après intégration de ces fichiers, le schéma cible est **V11**. La migration et ses tests sont implémentés ; l'intégration locale et le commit restent à effectuer par le développeur.

**État transitoire : ne pas démarrer cette tranche contre les bases réelles.** Le wizard actuel écrit encore la préférence IA dans les anciens contextes ; son adaptation à `guild_settings` est le prochain chantier. Le runtime générique reste à construire. Les anciens moteurs spécialisés ont déjà été retirés de cette branche : leurs descriptions ci-dessous servent de référence historique, pas de garantie de disponibilité.

Validation locale sur données synthétiques : **488 tests réussis**, contre 444 au checkpoint initial, Ruff sans erreur. Aucun test Discord réel ni migration des bases de production/développement n'a été effectué.

Lire [le contrat et la passation de cette tranche](06_Migration_V11_Contrat_et_Passation.md) pour les décisions récentes, les limites, les fichiers et les commandes de validation. Ce complément actualise les sections antérieures concernant la prochaine migration et la configuration IA.


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

