# Documentation de Claviger

Ce dossier regroupe la documentation technique, historique et opérationnelle du projet.

## Organisation

- `V1/` conserve les documents liés à la première version et aux audits réalisés sur cette base.
- `V1.1/` documente l'évolution multi-guild, la configuration générique et les décisions structurantes de la V1.1.
- `development/` contient les pointeurs vers les conventions partagées et les compléments propres à Claviger.

## Conventions transverses

Les règles communes à plusieurs applications sont maintenues dans
[NexusPrincipia](https://github.com/Yrekk/NexusPrincipia), notamment :

- mode opératoire Dev + IA ;
- bootstrap de projet / Solution Technique / prompt maître ;
- continuité et passation intersession ;
- conventions de documentation ;
- conventions Python ;
- Debug & Observabilité.

Claviger ne doit pas maintenir une copie divergente de ces règles.

Les règles propres à Claviger restent dans ce dépôt : branches de travail,
promotion vers Succumbrae, contraintes Discord, migrations SQLite, workflows,
recovery, versionnement et décisions fonctionnelles.

## Priorité des sources

En cas de contradiction :

```text
code actuel de la branche
→ décisions explicites les plus récentes
→ point de reprise / suivi courant
→ documentation projet Claviger
→ Solution Technique / prompt maître spécifiques
→ conventions NexusPrincipia
→ documents historiques
```

Une contradiction importante doit être signalée plutôt que corrigée
silencieusement.

Le `README.md` principal à la racine du dépôt reste le document vivant du
produit.
