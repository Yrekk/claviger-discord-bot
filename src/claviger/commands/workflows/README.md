> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.


# Commandes de workflows

Ce sous-dossier regroupe les commandes Discord qui exposent un workflow utilisateur.

Exemples historiques :

- `/membre` ;
- `/noctis`.

À terme, ces commandes doivent devenir des façades fines autour du système de workflows génériques.

Elles traduisent une interaction Discord en appel applicatif mais ne doivent pas porter elles-mêmes la persistance, la planification des rôles ou le provisioning.
