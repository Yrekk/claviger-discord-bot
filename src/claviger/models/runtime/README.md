> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# Models runtime

Modèles décrivant l'état d'exécution et de diagnostic de l'application :

- identité Discord de l'application ;
- identité locale d'une guild ;
- état runtime global de l'application (normal / recovery / minimal / hard stop) ;
- confiance dans l'ownership de la base applicative ;
- readiness ;
- état runtime par guild ;
- configuration IA partagée au niveau d'une guild ;
- inspection de la configuration d'une guild ;
- métriques de configuration ;
- inspection de la policy effective pendant la phase de compatibilité ;
- demandes de restart.

Ils ne représentent pas un workflow métier : ils décrivent l'état nécessaire au fonctionnement et au diagnostic du bot lui-même.
