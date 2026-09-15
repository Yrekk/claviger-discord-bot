> **Réorganisation de fin V1.1**
>
> Ce dossier fait partie de l'arborescence cible. Tant que la migration n'est pas terminée,
> certains fichiers correspondant à cette responsabilité peuvent encore se trouver dans le dossier parent.
> Les déplacements seront réalisés progressivement avec mise à jour des imports et des tests.

# Services ADMIN

Services responsables du pipeline de configuration ADMIN d'une guild.

Le flux général est :

```text
Discord réel
→ discovery
→ reconciliation
→ choix humain si nécessaire
→ provisioning
→ persistence
```

Ils ne doivent pas intégrer leur propre logique d'interface Discord : l'UI et les commandes consomment ces services.
