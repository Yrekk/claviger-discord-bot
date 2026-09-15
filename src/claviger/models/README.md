# Models

Un **model** représente une donnée, un état ou un concept utilisé par l'application.

Les modèles servent à rendre explicite ce qui circule entre les différentes couches :

- configuration ;
- résultat de discovery ;
- plan de mutation ;
- état runtime ;
- résultat d'exécution ;
- définition de workflow.

Un model ne doit généralement pas devenir un composant qui orchestre les I/O ou les mutations externes.

## Sous-domaines cibles

- `admin/`
- `catalogs/`
- `context/`
- `roles/`
- `runtime/`
- `workflows/`

Cette séparation facilite la lecture d'un dossier qui contient désormais plusieurs dizaines de modèles.
