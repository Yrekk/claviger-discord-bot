import discord
from discord import app_commands

from claviger.commands.role_test import create_role_test_group
from claviger.commands.say import create_say_command
from claviger.config import (
    get_discord_guild_id,
    get_test_role_id,
)
from claviger.services.role_manager import RoleManager


class ClavigerBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

        self.guild_id = get_discord_guild_id()
        self.test_role_id = get_test_role_id()

        self.role_manager = RoleManager()

        guild = discord.Object(id=self.guild_id)

        self.tree.add_command(
            create_role_test_group(
                self.role_manager,
                self.test_role_id,
         ),
            guild=guild,
        )
        self.tree.add_command(
            create_say_command(),
            guild=guild,
        )

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.guild_id)

        synced = await self.tree.sync(guild=guild)

        print(f"Commandes synchronisées : {len(synced)}")

    async def on_ready(self) -> None:
        if self.user is None:
            return

        print(f"Claviger connecté en tant que {self.user} ({self.user.id})")
        print(f"Serveurs accessibles : {len(self.guilds)}")