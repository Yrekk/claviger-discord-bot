# Database

Ce dossier contient l'infrastructure SQLite de Claviger.

Il est responsable notamment de :

- l'ouverture des connexions ;
- l'initialisation et la migration du schéma ;
- la lecture de l'état technique de la base.

Il ne contient pas toute la logique de persistance métier.

Les opérations liées à un agrégat ou une configuration précise sont exposées par les `repositories/`.

```text
service
   ↓
repository
   ↓
database connection / schema
   ↓
SQLite
```
