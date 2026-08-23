import discord
from discord import app_commands

# Commands
from claviger.commands.claviger import create_claviger_group
from claviger.commands.role_test import create_role_test_group
from claviger.commands.say import create_say_command

# Config
from claviger.config import (
    get_admin_report_forum_id,
    get_database_path,
    get_discord_guild_id,
    get_test_role_id,
)

# Database
from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.database.status import DatabaseStatusService

# Policies
from claviger.policies.policy_resolver import PolicyResolver

# Reporting
from claviger.reporting.discord_forum import DiscordForumReporter
from claviger.reporting.python_logger import PythonLoggingReporter
from claviger.reporting.reporter import Reporter
from claviger.reporting.service import ReportService

# Repositories
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)

# Services
from claviger.services.authorization import AuthorizationService
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService
from claviger.services.role_manager import RoleManager
from claviger.services.say import SayService


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
        self.say_service = SayService()
        self.role_classifier = RoleClassifier()

        self.database = DatabaseConnection(
            get_database_path(),
        )

        self.database_schema = DatabaseSchema(
            self.database,
        )

        self.database_status_service = DatabaseStatusService(
            self.database,
            self.database_schema,
        )

        self.guild_policy_repository = GuildPolicyRepository(
            self.database,
        )

        self.policy_resolver = PolicyResolver(
            repository=self.guild_policy_repository,
            fallback_guild_id=self.guild_id,
        )

        reporters: list[Reporter] = [
            PythonLoggingReporter(),
        ]

        admin_report_forum_id = get_admin_report_forum_id()

        if admin_report_forum_id is not None:
            reporters.append(
                DiscordForumReporter(
                    client=self,
                    forum_channel_id=admin_report_forum_id,
                )
            )

        self.report_service = ReportService(
            reporters=reporters,
        )

        guild = discord.Object(
            id=self.guild_id,
        )

        self.tree.add_command(
            create_role_test_group(
                self.role_manager,
                self.test_role_id,
            ),
            guild=guild,
        )

        self.tree.add_command(
            create_say_command(
                self.authorization_service,
                self.say_service,
            ),
            guild=guild,
        )

        self.tree.add_command(
            create_claviger_group(
                self.role_discovery_service,
                self.policy_resolver,
                self.role_classifier,
                self.database_schema,
                self.database_status_service,
                self.report_service,
            ),
            guild=guild,
        )

    async def setup_hook(self) -> None:
        guild = discord.Object(
            id=self.guild_id,
        )

        synced = await self.tree.sync(
            guild=guild,
        )

        print(
            f"Commandes synchronisées : {len(synced)}"
        )

    async def on_ready(self) -> None:
        if self.user is None:
            return

        print(
            f"Claviger connecté en tant que "
            f"{self.user} ({self.user.id})"
        )
        print(
            f"Serveurs accessibles : {len(self.guilds)}"
        )