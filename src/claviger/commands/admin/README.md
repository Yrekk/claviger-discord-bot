> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.


# Commandes ADMIN

Ce sous-dossier regroupe les commandes administratives de Claviger.

Il contient notamment les commandes ou groupes liés à :

- la configuration du serveur, avec `config-server` comme adaptateur Discord du parcours ADMIN → IA → workflows ;
- la base de données ;
- le diagnostic ;
- les rôles administratifs ;
- le reporting ;
- le restart et les opérations de recovery.

Une commande placée ici peut être administrative sans pour autant être autorisée partout : les contrôles d'autorisation et les restrictions de contexte restent des responsabilités explicites du runtime et des services concernés.

La logique métier ne doit pas être réimplémentée dans ces handlers.
