# Reporting

Ce dossier contient l'infrastructure de reporting et de journalisation structurée.

Claviger distingue :

```text
réponse utilisateur
→ ce que l'utilisateur doit savoir

logging Python
→ diagnostic technique

reporting Discord
→ suivi administratif best effort
```

Le reporting Discord ne doit pas devenir la seule trace d'un incident.

Une défaillance de destination Discord ne doit pas transformer silencieusement une opération métier réussie en faux échec.
