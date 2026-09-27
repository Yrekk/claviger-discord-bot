# Complément Claviger — workflow de développement

**Statut :** règle projet active  
**Portée :** Claviger V1.1 et promotions jusqu'à production  
**Socle transverse :**
[NexusPrincipia — Mode opératoire Dev + IA](https://github.com/Yrekk/NexusPrincipia/blob/main/docs/development/ai-development-operating-model.md)

Ce document contient uniquement les règles propres à Claviger ou les
précisions nécessaires au workflow courant.

## Branche active et point de reprise

Branche de développement actuelle :

```text
feature/v11-hardening-recovery
```

Point de reprise opérationnel :

```text
documentations/V1.1/09_SUIVI_HARDENING_RECOVERY_V1_1.md
```

L'ancienne branche `refactor/generic-workflows-v11` est historique. Elle ne
doit plus recevoir les changements courants de la V1.1.

Avant toute écriture distante :

1. vérifier le HEAD réel de la branche active ;
2. si le développeur annonce un push, relire immédiatement le HEAD ;
3. comparer avant remplacement si le HEAD a bougé.

## Workflow courant

Pour une tranche significative :

```text
besoin / contrat déjà cadré
→ rappel du scope et des risques
→ validation architecturale si nécessaire
→ production code + tests + docs
→ commit/push sur la branche de travail autorisée
→ pull/review locale du développeur
→ tests ciblés
→ Ruff + pytest complet par le développeur
→ smoke réel si nécessaire
→ acceptation explicite
→ fermeture documentaire de la tranche
```

Une Solution Technique complète n'est pas recréée pour chaque sous-tranche déjà
couverte par l'audit, la roadmap ou un contrat validé. Elle est attendue pour
une nouvelle version, un nouveau sous-système, une fonctionnalité structurante
ou un refactor de fond.

## Écriture Git directe

Lorsque le développeur autorise explicitement l'écriture sur la tranche
courante, l'assistante peut :

- modifier les fichiers nécessaires ;
- créer un commit cohérent ;
- pousser sur la branche de travail active.

Cette autorisation ne vaut jamais autorisation de merge, de promotion ou de
déploiement.

Aucun merge vers `develop`, `deploy/succumbrae` ou `main` sans décision
explicite du développeur.

## Chaîne de promotion V1.1

Après fermeture et acceptation de la branche hardening :

```text
feature/v11-hardening-recovery
→ develop
→ deploy/succumbrae
→ déploiement réel sur Succumbrae
→ smoke production
→ main
```

`main` représente un état déjà validé en conditions réelles.

`deploy/succumbrae` est la branche de release/déploiement ; elle ne doit pas
être contournée pour publier directement depuis `develop` ou `main`.

## Validation locale

Pour Claviger, l'assistante fournit en priorité les **tests ciblés** qui
protègent le changement qu'elle vient de produire.

Le développeur exécute de son côté, selon la convention établie :

```text
Ruff
pytest complet
```

Il n'est donc pas nécessaire de répéter mécaniquement ces deux commandes après
chaque micro-correction, sauf si elles font partie d'un diagnostic précis ou si
le développeur les demande.

Après une manipulation du dépôt, rappeler :

```text
git diff --check
git status --short
```

Pour la synchronisation locale, indiquer simplement **git pull**.

## Revue pédagogique

Après une tranche cohérente :

- expliquer ce qui a changé et pourquoi ;
- identifier les fichiers/responsabilités importants ;
- expliquer le flux avant/après ;
- préciser le risque évité et ce que couvrent les tests ;
- poser une courte question conceptuelle lorsqu'elle aide réellement à
  conserver la carte mentale du système.

La question n'est ni un examen ni une gate.

## Hardening V1.1

Pendant H1–H5 :

- le fichier
  `documentations/V1.1/09_SUIVI_HARDENING_RECOVERY_V1_1.md` est mis à jour
  au démarrage et à la fermeture d'une sous-tranche significative ;
- les décisions de recovery/sécurité sont documentées dans l'audit et/ou le
  suivi ;
- une bonne idée non bloquante va au backlog plutôt que d'élargir
  silencieusement la tranche ;
- H4/H5 doivent rester compatibles avec la direction d'observabilité partagée
  dans NexusPrincipia sans anticiper la Web Admin.

## Smoke réel

Avant un smoke Discord ou Succumbrae, rappeler :

- objectif ;
- principaux composants concernés ;
- comportement attendu ;
- scénario à exécuter ;
- point d'arrêt en cas d'anomalie.

Les smokes Laboratorium, seconde guild et Succumbrae complètent les tests
automatisés ; ils ne sont pas remplacés par eux.

## Environnements et secrets

Les secrets restent hors Git et hors image Docker.

Le déploiement production doit utiliser son profil de configuration propre ; il
ne doit jamais reconstruire implicitement une configuration production à
partir du profil de développement.

## Continuité intersession

Une nouvelle session suit le socle NexusPrincipia puis applique le delta
Claviger :

```text
README projet
→ suivi/handoff V1.1 courant
→ tranche active
→ branche + HEAD réel
→ documents de décision nécessaires
→ fichiers concernés
```

La conversation n'est jamais la seule mémoire opérationnelle.
