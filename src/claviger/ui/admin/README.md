> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# UI ADMIN

Composants Discord utilisés pour guider la configuration ADMIN d'une guild et l'étape IA partagée de `config-server`.

Ils présentent les choix, recueillent la décision humaine et appellent les services de configuration.

Ils ne doivent pas dupliquer discovery, reconciliation, validation métier ou provisioning.
