# Intégration dans `src/claviger/bot.py`

Le ZIP ajoute la couche d'observabilité, mais `bot.py` doit sélectionner le nouvel arbre de commandes et transmettre l'événement public de complétion de discord.py.

Trois modifications très localisées sont nécessaires.

## 1. Importer l'arbre Claviger

Dans la section `# Reporting`, ajouter avant `DiscordForumReporter` :

```python
from claviger.reporting.command_tree import ClavigerCommandTree
```

La section commence donc par :

```python
# Reporting
from claviger.reporting.command_tree import ClavigerCommandTree
from claviger.reporting.discord_forum import DiscordForumReporter
```

## 2. Remplacer la construction du `CommandTree`

Dans `ClavigerBot.__init__`, remplacer la construction complète :

```python
self.tree = app_commands.CommandTree(
    self,
)
```

par :

```python
self.tree = ClavigerCommandTree(
    self,
)
```

`app_commands` reste importé dans `bot.py`, car il sert au type du callback de complétion ci-dessous.

## 3. Ajouter le callback de complétion

Dans `ClavigerBot`, juste avant `on_ready()` par exemple, ajouter :

```python
async def on_app_command_completion(
    self,
    interaction: discord.Interaction,
    command: app_commands.Command | app_commands.ContextMenu,
) -> None:
    """Record one application command that completed without an uncaught error."""

    await self.tree.record_completion(
        interaction,
    )
```

Le paramètre `command` fait partie du contrat de l'événement discord.py. Claviger n'en a pas besoin pour l'audit : le chemin de commande est reconstruit depuis l'interaction sans lire les valeurs des arguments.
