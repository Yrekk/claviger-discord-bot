# Commands

Les commandes constituent les points d'entrée Discord de Claviger.

Une commande doit principalement :

1. recevoir l'interaction Discord ;
2. vérifier le contexte minimal ;
3. transformer les données d'entrée ;
4. appeler les services appropriés ;
5. transformer le résultat en réponse Discord.

Elle ne doit pas devenir la couche qui contient toute la logique métier.

## Sous-domaines cibles

- `admin/` : administration, recovery et diagnostic.
- `workflows/` : façades Discord des workflows utilisateur.
- `general/` : commandes publiques simples qui ne constituent pas un workflow métier complet.
