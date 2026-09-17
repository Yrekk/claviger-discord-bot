# Complément Claviger — workflow par branches feature

**Statut :** règle projet active  
**Date :** 17 septembre 2026  
**Portée :** développement Claviger V1.1 jusqu'à fermeture de la branche `refactor/generic-workflows-v11`.

Ce document complète `MODE_OPERATOIRE_COLLABORATION_DEV_IA.md` pour Claviger. En cas de contradiction avec l'ancien « Complément de collaboration — 17 septembre 2026 » présent dans ce document générique, **le présent fichier prévaut pour Claviger**.

## Workflow courant

Pour toute tranche significative :

```text
branche feature dédiée
→ production code/tests/docs par l'assistante
→ commit/push sur la feature
→ pull local du développeur
→ brief pédagogique
→ validation locale du développeur
→ smoke Discord si nécessaire
→ corrections sur la feature
→ merge uniquement après acceptation explicite du développeur
```

La branche d'intégration actuelle est :

```text
refactor/generic-workflows-v11
```

`develop` reste hors périmètre jusqu'à la fermeture fonctionnelle de V1.1.

## Répartition des responsabilités

### Assistante

- vérifier le HEAD distant avant de travailler ;
- produire les modifications substantielles ;
- écrire/adapter les tests ;
- documenter la tranche ;
- créer des commits cohérents sur la branche feature ;
- expliquer les responsabilités, flux et risques ;
- ne jamais merger seule vers la branche d'intégration ;
- ne jamais toucher `develop` sans décision explicite du développeur.

### Développeur

- arbitrer produit et architecture ;
- pull/review localement ;
- exécuter les tests et smoke tests ;
- challenger les choix ;
- décider si la tranche est acceptée ;
- décider du merge.

## Ordre de validation

Donner d'abord :

```text
tests ciblés
→ Ruff
→ pytest complet
```

Si cette séquence est verte, donner ensuite séparément :

```text
git diff --check
```

puis :

```text
git status --short
```

Si le développeur indique avoir atteint les dernières étapes sans signaler d'échec, considérer la séquence précédente comme exécutée et verte.

## Brief avant smoke

Avant un smoke réel, rappeler au minimum :

- objectif du changement ;
- principaux fichiers/responsabilités ;
- flux avant/après ;
- résultat attendu ;
- point d'arrêt en cas d'anomalie.

## Questions pédagogiques

Poser occasionnellement une question courte quand elle aide réellement à conserver le modèle mental du système. Ne pas répéter une question déjà traitée ni transformer chaque tranche en quiz obligatoire.

## Continuité de session

Quand une session devient longue ou approche de sa limite :

1. mettre à jour la passation V1.1 courante ;
2. noter branche et dernier commit fonctionnel validé ;
3. distinguer clairement `validé`, `implémenté mais pas smoké`, `décidé mais pas implémenté` ;
4. écrire la prochaine tranche exacte ;
5. conserver les anomalies observées et les smoke tests restant à faire.

Une nouvelle session doit relire la passation puis vérifier le code réel avant de continuer.
