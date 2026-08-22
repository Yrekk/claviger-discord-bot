import discord
from discord import app_commands
##commands
from claviger.commands.role_test import create_role_test_group
from claviger.commands.say import create_say_command
##config
from claviger.config import (
    get_discord_guild_id,
    get_test_role_id,
)
from claviger.commands.claviger import create_claviger_group
##services  
from claviger.services.role_manager import RoleManager
from claviger.services.role_discovery import RoleDiscoveryService
from claviger.services.authorization import AuthorizationService

class ClavigerBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

        self.guild_id = get_discord_guild_id()
        self.test_role_id = get_test_role_id()

        self.role_manager = RoleManager()
        self.role_discovery_service = RoleDiscoveryService()
        self.authorization_service = AuthorizationService()

        guild = discord.Object(id=self.guild_id)

        self.tree.add_command(
            create_role_test_group(
                self.role_manager,
                self.test_role_id,
         ),
            guild=guild,
        )

        self.tree.add_command(
            create_say_command(self.authorization_service),
            guild=guild,
        )

        self.tree.add_command(
            create_claviger_group(
                self.role_discovery_service,
            ),
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