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
→ PR/merge uniquement après acceptation explicite du développeur
```

La branche d'intégration actuelle est :

```text
refactor/generic-workflows-v11
```

`develop` reste hors périmètre jusqu'à la fermeture fonctionnelle de V1.1.

## Chaîne de branches après fermeture V1.1

La chaîne de promotion validée pour Claviger est :

```text
feature/*
→ PR vers refactor/generic-workflows-v11
→ fermeture fonctionnelle V1.1
→ PR vers develop
→ PR/promotion vers deploy/succumbrae
→ déploiement sur Succumbrae
→ smoke et validation production
→ seulement après validation à 100 % : promotion vers main
```

`main` est la branche **STABLE**. Elle ne sert pas de branche de validation de déploiement et ne reçoit pas du code simplement parce que `develop` est vert.

`deploy/succumbrae` est la branche de release/déploiement du serveur Succumbrae. Le CD doit donc cibler cette branche, pas `main`.

Une anomalie découverte sur Succumbrae doit être corrigée avant promotion vers `main` ; `main` doit rester représentative d'un état déjà validé en conditions réelles.

## Environnements `.env`

Claviger utilise désormais un sélecteur d'environnement (`CLAVIGER_ENV`) afin de distinguer notamment développement et production.

Le déploiement ne doit plus reconstruire un `.env` de production à partir d'un `.env` de développement. La procédure cible est :

```text
configuration production existante
→ copie/reprise du profil de production (.env.production)
→ adaptation du .env / sélecteur d'environnement pour le conteneur cible
→ validation docker compose
→ démarrage
```

Les secrets restent hors Git et hors image Docker. Lors d'une évolution des variables attendues, comparer la configuration de production avec `.env.example` et mettre à jour le serveur avant le nouveau conteneur.

## Répartition des responsabilités

### Assistante

- vérifier le HEAD distant avant de travailler ;
- produire les modifications substantielles ;
- écrire/adapter les tests ;
- documenter la tranche ;
- créer des commits cohérents sur la branche feature ;
- expliquer les responsabilités, flux et risques ;
- ne jamais merger seule vers la branche d'intégration ;
- ne jamais promouvoir vers `develop`, `deploy/succumbrae` ou `main` sans décision explicite du développeur.

### Développeur

- arbitrer produit et architecture ;
- pull/review localement ;
- exécuter les tests et smoke tests ;
- challenger les choix ;
- décider si la tranche est acceptée ;
- décider des PR/merges et de chaque promotion de branche ;
- valider le déploiement réel avant toute promotion vers `main`.

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
5. conserver les anomalies observées et les smoke tests restant à faire ;
6. rappeler la chaîne de promotion jusqu'à `main` si la session approche de la fermeture/release.

Une nouvelle session doit relire la passation puis vérifier le code réel avant de continuer.
