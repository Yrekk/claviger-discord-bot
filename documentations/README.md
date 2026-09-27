# Documentation de Claviger

Ce dossier regroupe la documentation technique, historique et opérationnelle du projet.

## Organisation

- `V1/` conserve les documents liés à la première version et aux audits réalisés sur cette base.
- `V1.1/` documente l'évolution multi-guild, la configuration générique et les décisions structurantes de la V1.1.
- `development/` contient les pointeurs vers les conventions partagées et les éventuels compléments propres à Claviger.

## Conventions transverses

Les règles communes à plusieurs applications sont maintenant maintenues dans [NexusPrincipia](https://github.com/Yrekk/NexusPrincipia), notamment :

- mode opératoire Dev + IA ;
- conventions de documentation ;
- continuité/passation ;
- conventions Python ;
- Debug & Observabilité.

Claviger ne doit pas maintenir une copie divergente de ces règles.

La documentation historique explique comment certaines décisions ont été prises. Elle ne remplace pas le code actuel.

En cas de contradiction, la priorité reste :

```text
code actuel
→ décisions les plus récentes
→ passation récente
→ documentation projet
→ conventions NexusPrincipia
→ documents historiques
```

Le `README.md` principal à la racine du dépôt reste le document vivant du produit.
