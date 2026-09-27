# Passation — Console Admin / diagnostics runtime V1.3

**Date :** 27 septembre 2026  
**Cible principale :** V1.3 — Web Admin  
**Contexte actuel :** V1.1 hardening/recovery

## Intention

La future interface Admin doit fournir un onglet de diagnostics runtime utilisable comme première couche de debugging en production, sans devoir ouvrir un shell sur Succumbrae ni arrêter Claviger.

La référence d'ergonomie est proche d'une console runtime type MuleSoft : flux live, filtres structurés, sélection d'une application/instance et activation temporaire d'un niveau de log plus verbeux.

## Principe d'architecture

L'Admin ne doit pas lire/scraper directement stdout.

Claviger doit produire des événements/logs structurés qui peuvent alimenter plusieurs sorties :

```text
événement runtime structuré
        ├── console locale
        ├── fichier local persistant
        └── flux live Admin
```

La console locale, le fichier et l'Admin sont donc trois rendus/transports d'une même information, pas trois systèmes de log différents.

Le logger Python application-wide existant reste distinct du reporter Discord. Une panne de Discord ou de l'Admin ne doit jamais supprimer la trace locale.

## Niveaux

Flux live normal vers l'Admin :

- INFO ;
- WARNING ;
- ERROR ;
- CRITICAL.

Par défaut :

- DEBUG reste local ;
- TRACE/équivalent très verbeux reste local si introduit plus tard.

L'Admin doit pouvoir demander temporairement un niveau DEBUG pour une application/instance précise, sans restart si l'architecture de logging le permet.

Ce mode DEBUG distant doit avoir :

- une activation explicite ;
- une durée/TTL obligatoire ;
- un retour automatique au niveau normal ;
- une trace d'audit de l'activation et de sa fin ;
- aucun secret exposé.

## Filtres Admin attendus

Au minimum :

- application / composant ;
- instance ou machine ;
- guild ;
- niveau ;
- event/category ;
- correlation_id ;
- plage de temps.

La recherche texte reste utile en complément, mais ne remplace pas les champs structurés.

## Champs de diagnostic utiles

Sans figer dès maintenant un schéma définitif, les événements devraient pouvoir porter selon le contexte :

```text
timestamp
level
component
event_id
message
guild_id
actor/user_id si pertinent
correlation_id
exception / cause
runtime_mode
```

Les données sensibles doivent être filtrées/redactées avant sortie locale ou distante.

## Décision de timing

### Pendant H4/H5 hardening

Ne pas dériver la V1.1 vers une implémentation Web Admin ou un transport live.

En revanche, si H4/H5 touche déjà au logging/reporting :

- conserver/renforcer un point d'entrée de logging centralisé ;
- préférer des événements et champs structurés aux chaînes ad hoc ;
- éviter les nouveaux `print()` ou accès directs console ;
- conserver les logs locaux même si un reporter externe échoue ;
- ajouter un `correlation_id` là où une opération multi-étapes devient difficile à diagnostiquer, si cela reste local et proportionné à la tranche.

Ces adaptations sont acceptables si elles servent directement le hardening ; elles ne doivent pas devenir un chantier V1.3 anticipé.

### Après le hardening / audit final V1.1

Lors de la passe finale « logs / reporting » déjà prévue dans la roadmap :

1. inventorier les sorties console / logger / reporting ;
2. vérifier qu'aucune information critique n'existe uniquement dans stdout ;
3. identifier les événements qui gagneraient à avoir un `event_id` stable ou des champs structurés ;
4. confirmer la persistance locale et la rotation des logs ;
5. préparer les frontières nécessaires à la V1.3 sans implémenter l'UI ni le streaming live.

### V1.3

Implémenter réellement :

- transport temps réel Admin ;
- onglet Diagnostics/Runtime Logs ;
- filtres structurés ;
- activation DEBUG temporaire avec TTL ;
- sélection application/instance/guild ;
- historique exploitable depuis les logs persistants ;
- redaction des secrets et permissions d'accès.

Le choix SSE/WebSocket/autre n'est pas décidé ici : il doit être choisi quand l'API Admin et ses contraintes seront concrètes.

## Invariant

Le mécanisme de diagnostics ne doit jamais devenir une dépendance du métier :

```text
métier / hardening
→ continue même si flux Admin indisponible

logging local
→ reste disponible

flux Admin
→ confort opérationnel et diagnostic distant
```

La perte du canal Admin ne doit donc pas casser Claviger ni masquer les erreurs locales.
