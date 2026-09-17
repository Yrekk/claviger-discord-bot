# Services runtime

Services nécessaires au cycle de vie, à l'identité et à la sécurité d'exécution de l'application.

Ce domaine regroupe notamment :

- l'identité Discord de l'application et des guilds ;
- la readiness d'une guild ;
- l'ownership de la base de données ;
- la configuration IA partagée d'une guild, sa validation live et le provisioning de son rôle réservé ;
- l'inspection de configuration runtime ;
- les contrôles d'autorisation transversaux ;
- le bootstrap de policy encore conservé pendant la phase de compatibilité.

Ces services préparent et vérifient un environnement sûr avant que les workflows normaux puissent être exposés.
