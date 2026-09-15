# Tests

La suite de tests suit autant que possible l'arborescence du code source.

Objectif :

```text
src/claviger/services/workflows/foo_service.py
→ tests/services/workflows/test_foo_service.py
```

Cette convention permet de retrouver rapidement les tests à adapter lorsqu'un composant change.

## Exceptions

Certains tests restent volontairement transversaux lorsqu'ils couvrent :

- le runtime global ;
- le bootstrap de `ClavigerBot` ;
- plusieurs couches en même temps ;
- un scénario d'intégration qui ne correspond pas à un seul module.

La réorganisation de fin V1.1 doit rapprocher encore `tests/` de `src/claviger/` sans déplacer tous les fichiers en une seule opération.
