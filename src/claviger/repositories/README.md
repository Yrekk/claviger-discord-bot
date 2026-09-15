# Repositories

Un **repository** encapsule l'accès aux données persistantes d'un domaine.

Il permet aux services de lire ou sauvegarder des données sans connaître partout :

- le SQL ;
- les tables ;
- la mécanique de connexion ;
- certains détails de transaction.

Un repository ne décide normalement pas du comportement métier : il applique un contrat de persistance.

## Sous-domaines cibles

- `admin/`
- `catalogs/`
- `context/`
- `runtime/`
- `workflows/`
