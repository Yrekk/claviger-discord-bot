# Database migrations

Ce dossier contient les transformations de données qui ne peuvent pas être exprimées proprement par une simple suite d'instructions SQL.

Chaque module est lié à une version de schéma précise et doit rester :

- atomique : il s'exécute dans la transaction ouverte par `DatabaseSchema` ;
- déterministe : une même base source produit le même résultat ;
- fail-closed : une donnée ambiguë ou invalide interrompt la migration avant toute destruction ;
- historique : les conventions de nommage anciennes peuvent être comprises ici, mais ne doivent pas contaminer le runtime générique.

Le schéma et l'ordre des versions restent définis dans `database/schema.py`.
