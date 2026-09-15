# Services

Un **service** porte une responsabilité applicative ou métier.

Selon son rôle, un service peut :

- calculer ;
- valider ;
- découvrir ;
- planifier ;
- coordonner ;
- provisionner ;
- exécuter un effet de bord contrôlé.

Le dossier `services/` ne doit pas redevenir un dossier fourre-tout.

Les services sont regroupés par domaine fonctionnel lorsque plusieurs composants travaillent sur le même sujet.

## Sous-domaines cibles

- `admin/`
- `catalogs/`
- `context/`
- `roles/`
- `runtime/`
- `workflows/`

Les rares services réellement transversaux et simples peuvent rester directement dans `services/`.
