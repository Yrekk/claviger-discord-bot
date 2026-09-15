> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# Services runtime

Services nécessaires au cycle de vie et à la sécurité d'exécution de l'application :

- identité Discord ;
- readiness ;
- ownership de la base ;
- bootstrap de configuration ;
- contrôles transversaux d'autorisation lorsque leur portée est runtime.

Ils préparent un environnement sûr avant que les workflows normaux puissent être exposés.
