# Prompt de reprise — Réorganisation de l'arborescence en fin de V1.1

Tu reprends Claviger à la fin fonctionnelle de la V1.1 pour effectuer une réorganisation **structurelle et documentaire** du dépôt.

## Source de vérité

- Dépôt : `Yrekk/claviger-discord-bot`
- Branche de développement : `develop`
- Avant toute proposition, relis le HEAD réel de `develop`.
- Si l'utilisateur indique qu'il vient de push, relis immédiatement le HEAD avant de continuer.

Lis également :

- `documentations/development/MODE_OPERATOIRE_COLLABORATION_DEV_IA.md`
- `documentations/V1.1/03_Arborescence_Cible_Fin_V1_1.md`
- le README principal ;
- les README locaux concernés par la tranche.

## Objectif

Réorganiser progressivement les dossiers devenus trop plats, notamment :

- `commands/`
- `models/`
- `repositories/`
- `services/`
- `ui/`

sans modifier volontairement le comportement fonctionnel de Claviger.

La nouvelle organisation doit rendre les domaines visibles et réduire les dossiers contenant de nombreux fichiers sans hiérarchie.

## Règle README

Chaque dossier et sous-dossier significatif doit posséder un `README.md` expliquant :

1. ce qu'est le type de composant concerné ;
2. pourquoi ce dossier existe ;
3. ce qui doit y être placé ;
4. ce qui ne doit pas y être placé ;
5. comment il collabore avec les autres couches.

Les README fournis dans le pack de préparation constituent la base à conserver et à ajuster si la réalité du code a évolué.

## Tests : OUI, une réorganisation est nécessaire

La structure des tests doit **ressembler autant que possible à `src`**.

But ergonomique :

```text
src/claviger/services/workflows/foo_service.py
tests/services/workflows/test_foo_service.py
```

Lorsque le développeur modifie un service, il doit pouvoir déduire immédiatement dans quel dossier chercher ses tests.

Les exceptions transversales restent autorisées lorsqu'elles sont justifiées et documentées, notamment `tests/runtime/` pour les scénarios de lifecycle et de composition de `ClavigerBot`.

Points déjà identifiés à normaliser :

- terminer le rangement de `tests/services/` ;
- créer le miroir `commands/general` et `commands/workflows` ;
- remplacer la convention `tests/repository/` par `tests/repositories/` ;
- remplacer `tests/test_policies/` par `tests/policies/` ;
- répartir `tests/models/` selon les sous-domaines de `src/claviger/models/` ;
- répartir `tests/ui/` selon les sous-domaines de `src/claviger/ui/`.

## Méthode obligatoire

Ne fais PAS un déplacement massif de tous les fichiers.

Travaille dossier par dossier ou domaine par domaine.

Pour chaque tranche :

1. présente les fichiers actuels concernés ;
2. indique leur destination ;
3. explique pourquoi chacun appartient à ce domaine ;
4. déplace seulement ce groupe cohérent ;
5. corrige les imports du code ;
6. déplace les tests correspondants ;
7. corrige les imports des tests ;
8. mets à jour les `__init__.py` uniquement si nécessaire ;
9. exécute les tests ciblés ;
10. exécute `python -m ruff check . --fix` ;
11. exécute `python -m pytest -q` ;
12. vérifie les README locaux ;
13. fournis le titre et le corps du commit recommandé.

Ne combine pas cette réorganisation avec un nouveau comportement métier sauf si une correction est indispensable pour conserver le fonctionnement existant.

## Pédagogie

À chaque déplacement, explique au développeur :

- ce qu'est le type de composant ;
- pourquoi le fichier change de dossier ;
- quel rôle il joue ;
- quels imports doivent changer ;
- quels tests le protègent.

Le développeur délègue une grande partie de la production du code mais doit rester capable de comprendre la structure et de corriger lui-même un import ou un test simple.

## README principal

Ne mets à jour le README principal avec la nouvelle arborescence qu'une fois la structure réellement appliquée et validée.

Il ne doit jamais décrire comme actuelle une structure seulement planifiée.

## Critère de réussite

La réorganisation est terminée lorsque :

- les dossiers principaux ne sont plus des listes plates difficiles à parcourir ;
- chaque domaine significatif possède son README ;
- les tests reflètent autant que raisonnablement possible `src` ;
- les imports sont propres ;
- Ruff est vert ;
- la suite complète est verte ;
- le README principal décrit la structure réellement en place ;
- un smoke test DEV confirme qu'aucun comportement n'a été cassé.
