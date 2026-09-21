# Résilience de l'état des rôles membres — orientation post-V1.1

## Statut

**Décision d'orientation : actée**  
**Implémentation : non commencée**  
**Version cible : à décider après fermeture de la V1.1**

Ce document conserve une direction de développement importante sans l'ajouter
silencieusement au scope de la V1.1.

La décision de versionnage sera prise après la V1.1 :

```text
si le chantier reste contenu
→ candidat pour la future V1.3

si le chantier devient structurant
→ version dédiée
→ la V1.3 actuellement prévue est décalée en V1.4
```

---

# 1. Pourquoi ce développement existe

Claviger doit devenir capable de distinguer :

```text
état attendu par Claviger
≠
état réellement observé sur Discord
```

pour les **rôles membres appartenant au périmètre Claviger**.

Le but n'est pas de sauvegarder tous les rôles Discord ni de devenir un miroir
général du serveur.

Le but est la résilience :

- détecter une attribution partielle ;
- détecter un drift membre ;
- exploiter le contexte d'un incident ;
- réconcilier sans supprimer des rôles hors périmètre ;
- garder une trace de la provenance des changements ;
- pouvoir réparer après une fenêtre de recovery/snapshot.

---

# 2. Principe d'autorité

En fonctionnement NORMAL :

```text
SQLite
→ source de vérité persistante de Claviger

Discord
→ état opérationnel réel à observer et réconcilier
```

La décision « qui a raison ? » ne doit pas reposer uniquement sur un
`LastModifiedDate`.

Le futur moteur devra exploiter au minimum :

- l'intention Claviger connue ;
- l'heure de dernière validation ;
- l'origine du changement ;
- les incidents de mutation partielle ;
- le mode runtime au moment du changement ;
- l'état Discord réellement observé.

---

# 3. Cas recovery / snapshot

Le snapshot a pour objectif de **maintenir les questionnaires disponibles**.

Contrat :

```text
SQLite non fiable
→ snapshot LKG explicitement accepté
→ configuration figée
→ questionnaires existants encore utilisables
→ mutations de rôles membres Discord autorisées si Discord est sain
```

Pendant cette fenêtre, pour les rôles membres gérés par Claviger :

```text
Discord = réalité opérationnelle temporaire
```

La date d'entrée en snapshot/recovery doit être connue.

Quand SQLite redevient saine, le futur moteur pourra comparer l'état persistant
antérieur et l'état Discord actuel. Les différences apparues pendant la fenêtre
de recovery sont destinées à être réconciliées **vers la persistence**, dans le
périmètre des rôles gérés par Claviger.

La règle métier réduit fortement les ambiguïtés : les modérateurs/utilisateurs
de confiance ne doivent pas recevoir de permissions Discord structurelles leur
permettant de contourner Claviger. L'owner conserve naturellement ses droits
Discord natifs.

---

# 4. Réconciliation planifiée

Cible envisagée :

```text
22 h 30
→ audit des membres connus / rôles Claviger
→ détection des écarts
→ décision de réconciliation selon provenance/contexte
→ notifications et reporting

23 h
→ backup SQLite
```

Le contrôle de 22 h 30 est une cible, pas encore une implémentation.

Si SQLite est encore indisponible :

```text
aucune écriture forcée
→ réconciliation différée
→ reprise au premier créneau sûr en mode NORMAL
```

Après une réconciliation susceptible d'avoir corrigé des accès, le membre doit
pouvoir recevoir un MP de Claviger l'invitant à vérifier ses accès.

Les événements doivent être visibles dans les surfaces ADMIN :

- `Activity` pour une réconciliation normale/attendue ;
- `Error` lorsqu'une incohérence ou un incident nécessite une attention
  humaine.

---

# 5. Persistance future — orientation, pas schéma figé

Une table membre + une colonne JSON de tous les rôles n'est pas retenue comme
contrat.

La direction préférée est relationnelle et limitée au périmètre Claviger, par
exemple :

```text
guild_member_workflow_state
- guild_id
- user_id
- workflow_key
- revision / timestamps / provenance

guild_member_workflow_roles
- guild_id
- user_id
- workflow_key
- role_id
```

Ce modèle reste indicatif jusqu'à la solution technique de la version qui
portera réellement ce développement.

---

# 6. Double panne : fallback hors SQLite

Un journal JSON ou équivalent hors SQLite **ne doit pas devenir une deuxième
base normale**.

Il n'est envisagé que si les deux conditions sont réunies :

```text
RECOVERY / SNAPSHOT
+
échec ou incertitude pendant la mutation Discord
```

Dans ce cas, le journal de secours doit rester :

- minimal ;
- atomique ;
- limité aux membres concernés ;
- limité aux opérations/roles nécessaires à la réconciliation ;
- supprimable/archivable après résolution ;
- incapable de devenir une source de vérité permanente.

Si Discord fonctionne normalement pendant le snapshot, **aucun journal JSON
général des membres n'est nécessaire** : Discord porte temporairement l'état
opérationnel des rôles membres.

---

# 7. Hors scope actuel

Ce développement ne doit pas être introduit dans H2 ou H4 par dérive de scope.

H2 reste centré sur :

- détection et reporting des mutations partielles ;
- réconciliation par relance du questionnaire.

H4 doit fournir :

- Last Known Good ;
- mode recovery ;
- maintien des questionnaires ;
- bornage temporel de la fenêtre snapshot ;
- primitives nécessaires à une future réconciliation ;
- backup SQLite.

Le moteur complet d'état attendu des membres et de réconciliation périodique
sera conçu après fermeture de la V1.1.
