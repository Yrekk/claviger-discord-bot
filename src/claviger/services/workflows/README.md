# Services de workflows

Ce dossier contient les implémentations canoniques des services génériques de workflow.

Un workflow représente un parcours applicatif configurable : à partir d'une définition, d'un contexte et de choix utilisateur, Claviger détermine les ressources et le comportement à appliquer.

Le flux conceptuel reste :

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

Les services de ce domaine ne doivent pas dépendre de noms de workflows historiques. Les noms, commandes, rôles et catalogues applicatifs sont des données de configuration ; ils ne constituent pas des branches métier codées en dur.

Pendant la réorganisation de fin V1.1, les anciens modules directement sous `services/` restent temporairement des façades d'import. Ils seront supprimés après migration complète des consommateurs vers les chemins canoniques.
