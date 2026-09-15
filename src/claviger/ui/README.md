# UI Discord

Ce dossier contient les composants d'interface Discord :

- views ;
- modales ;
- sessions d'interface ;
- composants interactifs.

L'UI traduit les modèles et résultats applicatifs dans les composants attendus par Discord.

Elle ne doit pas posséder sa propre logique parallèle de persistence ou de provisioning.

```text
UI Discord
    ↓
services métier
```

La future Web UI devra appeler les mêmes services plutôt que recopier cette logique.
