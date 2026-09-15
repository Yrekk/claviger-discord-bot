> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# Models runtime

Modèles décrivant l'état d'exécution de l'application :

- identité Discord de l'application ;
- identité locale d'une guild ;
- readiness ;
- état runtime par guild ;
- demandes de restart.

Ils ne représentent pas un workflow métier : ils décrivent l'état nécessaire au fonctionnement du bot lui-même.
