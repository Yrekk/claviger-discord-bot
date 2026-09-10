import discord
from discord import app_commands

# Commands
from claviger.commands.claviger_command import create_claviger_group
from claviger.commands.member_command import create_member_command
from claviger.commands.noctis_command import create_noctis_command
from claviger.commands.say import create_say_command

# Config
from claviger.config import (
    get_database_path,
    get_discord_bot_user_id,
    get_discord_guild_id,
    get_error_report_forum_id,
)

# Database
from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.database.status import DatabaseStatusService

# Policies
from claviger.policies.default_policy import SUCCUMBRAE_FALLBACK_POLICY
from claviger.policies.policy_resolver import PolicyResolver

# Reporting
from claviger.reporting.discord_forum import DiscordForumReporter
from claviger.reporting.python_logger import PythonLoggingReporter
from claviger.reporting.reporter import Reporter
from claviger.reporting.service import ReportService

# Repositories
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)
from claviger.services.adult_access_classifier import (
    AdultAccessClassifier,
)

# Services
from claviger.services.adult_access_questionnaire_service import (
    AdultAccessQuestionnaireService,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)
from claviger.services.authorization import AuthorizationService
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.services.catalog_registry_service import CatalogRegistry
from claviger.services.catalog_sync_coordinator_service import (
    CatalogSyncCoordinatorService,
)
from claviger.services.catalog_sync_planner_service import CatalogSyncPlanner
from claviger.services.guild_policy_bootstrap import (
    GuildPolicyBootstrapService,
)
from claviger.services.member_interest_questionnaire_service import (
    MemberInterestQuestionnaireService,
)
from claviger.services.member_role_executor_service import (
    MemberRoleExecutorService,
)
from claviger.services.member_role_planner_service import (
    MemberRolePlannerService,
)
from claviger.services.member_workflow_coordinator_service import (
    MemberWorkflowCoordinatorService,
)
from claviger.services.noctis_role_executor_service import (
    NoctisRoleExecutorService,
)
from claviger.services.noctis_role_planner_service import (
    NoctisRolePlannerService,
)
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.services.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService
from claviger.services.role_manager_service import RoleManager
from claviger.services.say import SayService


class ClavigerBot(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

        self.guild_id = get_discord_guild_id()
        self.expected_bot_user_id = get_discord_bot_user_id()

        self.role_manager = RoleManager()
        self.role_discovery_service = RoleDiscoveryService()
        self.authorization_service = AuthorizationService()
        self.say_service = SayService()
        self.role_classifier = RoleClassifier()
        self.adult_access_classifier = AdultAccessClassifier()

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

        self.interest_catalog_repository = InterestCatalogRepository(
            self.database,
        )

        self.access_catalog_repository = AccessCatalogRepository(
            self.database,
        )

        self.member_interest_questionnaire_service = MemberInterestQuestionnaireService(
            repository=self.interest_catalog_repository,
        )

        self.member_role_planner_service = MemberRolePlannerService()

        self.member_role_executor_service = MemberRoleExecutorService(
            role_manager=self.role_manager,
        )

        self.member_workflow_coordinator_service = MemberWorkflowCoordinatorService(
            questionnaire_service=(self.member_interest_questionnaire_service),
            planner_service=self.member_role_planner_service,
            executor_service=self.member_role_executor_service,
        )

        self.adult_access_workflow_service = AdultAccessWorkflowService(
            classifier=self.adult_access_classifier,
        )

        self.adult_access_questionnaire_service = AdultAccessQuestionnaireService(
            repository=self.access_catalog_repository,
            workflow_service=self.adult_access_workflow_service,
        )

        self.noctis_role_planner_service = NoctisRolePlannerService(
            workflow_service=self.adult_access_workflow_service,
        )

        self.noctis_role_executor_service = NoctisRoleExecutorService(
            role_manager=self.role_manager,
        )

        self.noctis_workflow_coordinator_service = NoctisWorkflowCoordinatorService(
            questionnaire_service=self.adult_access_questionnaire_service,
            planner_service=self.noctis_role_planner_service,
            executor_service=self.noctis_role_executor_service,
        )

        self.policy_resolver = PolicyResolver(
            repository=self.guild_policy_repository,
            fallback_guild_id=self.guild_id,
        )

        self.guild_policy_bootstrap_service = GuildPolicyBootstrapService(
            repository=self.guild_policy_repository,
            fallback_guild_id=self.guild_id,
            bootstrap_policy=SUCCUMBRAE_FALLBACK_POLICY,
        )

        self.catalog_registry = CatalogRegistry(
            interest_repository=self.interest_catalog_repository,
            access_repository=self.access_catalog_repository,
        )

        self.catalog_next_coordinator_service = CatalogNextCoordinatorService(
            registry=self.catalog_registry,
        )

        self.role_channel_discovery_service = RoleChannelDiscoveryService()

        self.catalog_sync_planner = CatalogSyncPlanner()

        self.catalog_sync_coordinator_service = CatalogSyncCoordinatorService(
            database=self.database,
            registry=self.catalog_registry,
            discovery_service=self.role_channel_discovery_service,
            planner=self.catalog_sync_planner,
        )

        reporters: list[Reporter] = [
            PythonLoggingReporter(),
        ]

        admin_report_forum_id = get_error_report_forum_id()

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
            create_say_command(
                self.authorization_service,
                self.say_service,
            ),
            guild=guild,
        )

        self.tree.add_command(
            create_member_command(
                self.policy_resolver,
                self.database_status_service,
                self.member_workflow_coordinator_service,
            ),
            guild=guild,
        )

        self.tree.add_command(
            create_noctis_command(
                self.noctis_workflow_coordinator_service,
                self.policy_resolver,
                self.database_status_service,
                self.report_service,
            ),
            guild=guild,
        )

        self.tree.add_command(
            create_claviger_group(
                self.role_discovery_service,
                self.policy_resolver,
                self.role_classifier,
                self.catalog_sync_coordinator_service,
                self.catalog_next_coordinator_service,
                self.guild_policy_bootstrap_service,
                self.database_schema,
                self.database_status_service,
                self.report_service,
            ),
            guild=guild,
        )

    def _validate_authenticated_bot_identity(self) -> None:
        """Ensure the authenticated Discord bot matches this environment."""

        if self.user is None:
            raise RuntimeError(
                "Discord bot identity is unavailable before command synchronization."
            )

        if self.user.id != self.expected_bot_user_id:
            raise RuntimeError(
                "Authenticated Discord bot identity does not match configuration. "
                f"Expected DISCORD_BOT_USER_ID={self.expected_bot_user_id}, "
                f"but Discord authenticated user ID {self.user.id}."
            )

    async def setup_hook(self) -> None:
        self._validate_authenticated_bot_identity()

        guild = discord.Object(
            id=self.guild_id,
        )

        synced = await self.tree.sync(
            guild=guild,
        )

        print(f"Commandes synchronisées : {len(synced)}")

    async def on_ready(self) -> None:
        if self.user is None:
            return

        print(f"Claviger connecté en tant que {self.user} ({self.user.id})")
        print(f"Serveurs accessibles : {len(self.guilds)}")
