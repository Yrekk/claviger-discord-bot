> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# Services de workflows

Ce sous-dossier regroupe les services qui configurent ou exécutent les workflows.

Un **workflow** représente un parcours applicatif configurable : à partir d'une définition, d'un contexte et de choix utilisateur, Claviger détermine le comportement à appliquer.

On y trouve conceptuellement :

```text
definition / configuration
        ↓
validation
        ↓
discovery / reconciliation
        ↓
questionnaire ou entrée utilisateur
        ↓
planning
        ↓
preflight
        ↓
execution
```

Les workflows historiques `/membre` et `/noctis` doivent progressivement devenir des façades/configurations de ce système générique, sans heuristique basée sur leurs noms.
