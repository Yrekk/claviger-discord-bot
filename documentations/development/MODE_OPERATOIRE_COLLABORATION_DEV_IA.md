# Mode opératoire de collaboration — Développement assisté par IA

Le mode opératoire générique n'est plus maintenu dans Claviger.

La source de vérité transverse est désormais **NexusPrincipia** :

- [Mode opératoire Dev + IA](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/ai-development-operating-model.md)
- [Démarrage de projet — Solution Technique + prompt maître](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/project-bootstrap.md)
- [Continuité / passation](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/session-continuity.md)
- [Conventions de documentation](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/documentation-conventions.md)
- [Conventions Python](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/languages/python.md)
- [Debug & Observabilité](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/architecture/debug-observability.md)

## Compléments propres à Claviger

Les règles qui diffèrent ou précisent le socle commun restent dans :

- [CLAVIGER_WORKFLOW_FEATURE_BRANCHES.md](CLAVIGER_WORKFLOW_FEATURE_BRANCHES.md)
- [ADMIN_RUNTIME_DIAGNOSTICS_V1_3.md](ADMIN_RUNTIME_DIAGNOSTICS_V1_3.md)

L'état opérationnel de la V1.1 est suivi dans :

- [09_SUIVI_HARDENING_RECOVERY_V1_1.md](../V1.1/09_SUIVI_HARDENING_RECOVERY_V1_1.md)

Les documents de version, la roadmap, les contraintes Discord, les migrations
SQLite, les règles de workflow et les décisions propres au bot restent dans ce
dépôt.

En cas de contradiction, le code courant et les décisions récentes de Claviger
priment sur une convention transverse générique.

Ce fichier reste volontairement un **pointeur local** : les règles génériques ne
doivent plus diverger entre Claviger, GameSaveSync, NexusPrincipia et les futurs
projets.
