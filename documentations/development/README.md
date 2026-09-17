# Développement et méthode de collaboration

Ce dossier contient les documents qui expliquent **comment travailler sur le projet**, plutôt que le fonctionnement fonctionnel d'une version précise de Claviger.

## Documents actifs

### `MODE_OPERATOIRE_COLLABORATION_DEV_IA.md`

Socle générique de collaboration entre le développeur et l'assistante IA :

- source de vérité ;
- petites tranches ;
- diagnostic avant correction ;
- niveau d'explication attendu ;
- tests et smoke tests ;
- documentation vivante ;
- passations ;
- README locaux ;
- miroir entre `src/` et `tests/`.

### `CLAVIGER_WORKFLOW_FEATURE_BRANCHES.md`

**Complément projet actif pour Claviger V1.1.**

Il définit le fonctionnement réellement utilisé depuis le 17 septembre 2026 :

```text
feature branch dédiée
→ production + commit/push par l'assistante
→ pull/review/tests/smoke par le développeur
→ merge uniquement après acceptation explicite
```

Pour Claviger, ce complément prévaut sur l'ancien paragraphe du mode opératoire générique indiquant que l'assistante ne commit/push jamais. Cette ancienne règle correspond à une phase de travail antérieure.

## Reprise après coupure de session

La méthode de collaboration ne suffit pas à connaître l'état fonctionnel du projet.

Pour reprendre Claviger V1.1, consulter aussi :

```text
documentations/V1.1/07_PASSATION_V11_CONFIG_SERVER_ET_SUITE_2026-09-17.md
```

La passation donne la branche, le dernier commit fonctionnel validé, les smoke tests effectués, les anomalies connues et la prochaine tranche exacte.
