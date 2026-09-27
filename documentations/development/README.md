# Développement et méthode de collaboration

Les conventions générales de développement assisté par IA sont centralisées
dans [NexusPrincipia](https://github.com/Yrekk/NexusPrincipia).

## Références communes

- [Mode opératoire Dev + IA](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/ai-development-operating-model.md)
- [Bootstrap projet / ST / prompt maître](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/project-bootstrap.md)
- [Continuité intersession](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/session-continuity.md)
- [Conventions de documentation](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/documentation-conventions.md)
- [Conventions Python](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/languages/python.md)
- [Debug & Observabilité](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/architecture/debug-observability.md)

Le fichier
[MODE_OPERATOIRE_COLLABORATION_DEV_IA.md](MODE_OPERATOIRE_COLLABORATION_DEV_IA.md)
reste comme point d'entrée local, mais il ne recopie plus le corpus partagé.

## Compléments Claviger

### `CLAVIGER_WORKFLOW_FEATURE_BRANCHES.md`

Complément projet actif :

- branche de travail courante ;
- règles de commit/push par l'assistante ;
- validation locale par le développeur ;
- chaîne de promotion jusqu'à `main` ;
- conventions de tests et de smoke propres à Claviger.

### `ADMIN_RUNTIME_DIAGNOSTICS_V1_3.md`

Direction propre à Claviger pour la future console runtime Admin :

- événements structurés ;
- persistance locale ;
- flux live futur ;
- DEBUG temporaire avec TTL ;
- frontières entre métier, logging et Admin.

La référence transverse d'observabilité reste NexusPrincipia ; ce document ne
conserve que la cible spécifique à Claviger.

## Point de reprise V1.1

Pour reprendre le développement courant, lire en priorité :

```text
documentations/V1.1/09_SUIVI_HARDENING_RECOVERY_V1_1.md
```

Puis vérifier la branche et le HEAD distants réels.

Le document `07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md` reste
historique : il ne doit plus servir de point de reprise principal.
