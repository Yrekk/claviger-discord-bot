# Reporting

Ce dossier contient l'infrastructure de reporting et de journalisation structurée.

Claviger distingue :

```text
réponse utilisateur
→ ce que l'utilisateur doit savoir

logging Python
→ diagnostic technique et audit local

reporting Discord
→ suivi administratif best effort
```

Le reporting Discord ne doit pas devenir la seule trace d'un incident.

Une défaillance de destination Discord ne doit pas transformer silencieusement une opération métier réussie en faux échec.

## Observabilité des commandes

`ClavigerCommandTree` centralise la frontière d'erreur des commandes Discord. Le runtime lui renvoie également l'événement public `on_app_command_completion`. La construction et le routage des événements sont délégués à `CommandObservabilityService`, afin de ne pas dupliquer cette responsabilité dans chaque commande.

La politique V1.1 est volontairement simple :

```text
commande terminée sans exception non gérée
→ INFO console
→ INFO report-activity si ADMIN est configuré

refus attendu par un check ayant déjà répondu
→ INFO console
→ INFO report-activity si ADMIN est configuré
→ aucun traceback discord.py

erreur non gérée
→ ERROR console avec traceback
→ ERROR report-error si disponible
```

Une commande qui traite elle-même un échec métier peut donc produire son propre événement d'erreur puis un événement générique « commande traitée ». Ce dernier signifie uniquement que le callback s'est terminé sans exception non gérée ; il ne prétend pas que l'opération métier a réussi.

Sur un serveur non encore configuré, `report-activity` et `report-error` n'existent pas encore. Les événements restent alors disponibles dans le logging Python sans transformer cet état normal de bootstrap en avertissement de reporting.

Les valeurs des arguments de commandes ne sont jamais journalisées par cette couche. Elles peuvent contenir des messages, prompts, secrets ou autres données utilisateur. Seuls l'identité de la commande et son contexte d'exécution sont enregistrés.

L'autocomplétion ne déclenche pas l'événement de complétion d'une commande et ne produit donc aucun rapport d'activité à chaque frappe clavier.


## Fallback humain sur drift ADMIN

Les incidents Discord utilisent une chaîne humaine explicite :

```text
forum ADMIN configuré
→ tentative de publication

succès
→ terminé

échec réel du forum
→ DM forcé à l'acteur de l'incident
→ warning Python sur le fallback
```

Le fallback DM ne se base donc plus uniquement sur la présence d'une
configuration ADMIN complète en SQLite. Une configuration persistée peut être
stale alors que le forum Discord a été supprimé, a changé de type ou refuse
l'opération.

Les événements `INFO` ne déclenchent pas de DM de secours : une panne du forum
d'activité reste observable dans les logs sans spammer les utilisateurs.
