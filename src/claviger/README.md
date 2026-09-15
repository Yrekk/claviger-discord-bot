# Package `claviger`

Ce dossier contient le package Python principal de Claviger.

Les fichiers situés directement ici sont réservés aux responsabilités globales telles que :

- le point d'entrée ;
- la composition de l'application ;
- la configuration globale ;
- les éléments qui ne correspondent pas à un sous-domaine suffisamment stable pour justifier leur propre package.

Les couches spécialisées sont réparties dans les dossiers documentés ci-dessous.

## Principes

```text
Discord / UI
    ↓
commands / ui
    ↓
services
    ↓
repositories / policies / reporting / database
```

Les `models` transportent les données entre ces couches.

Le but de cette arborescence n'est pas d'appliquer une Clean Architecture académique, mais de rendre les responsabilités et la navigation prévisibles.
