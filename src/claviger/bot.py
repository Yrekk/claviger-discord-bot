import logging

import discord
from discord import app_commands
from discord.http import Route

# Commands
from claviger.commands.claviger_command import create_claviger_group
from claviger.commands.member_command import create_member_command
from claviger.commands.noctis_command import create_noctis_command
from claviger.commands.say_command import create_say_command

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
from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)

# Models
from claviger.models.discord_runtime_identity_model import (
    DiscordRuntimeIdentity,
)
from claviger.models.runtime_restart_model import RuntimeRestartRequest

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
from claviger.repositories.database_ownership_repository import (
    DatabaseOwnershipRepository,
)
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)

# Services
from claviger.services.adult_access_classifier import (
    AdultAccessClassifier,
)
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
from claviger.services.database_ownership_service import (
    DatabaseOwnershipService,
    DatabaseOwnershipUnboundError,
)
from claviger.services.discord_identity_service import DiscordIdentityService
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
from claviger.services.say_service import SayService

logger = logging.getLogger(__name__)


class ClavigerBot(discord.Client):
    def __init__(
        self,
        *,
        startup_restart_request: RuntimeRestartRequest | None = None,
    ) -> None:
        intents = discord.Intents.default()

        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)

        self.guild_id = get_discord_guild_id()
        self.expected_bot_user_id = get_discord_bot_user_id()

        self.restart_requested = False
        self.pending_restart_request: RuntimeRestartRequest | None = None

        self.startup_restart_request = startup_restart_request
        self.started_from_restart = startup_restart_request is not None
        self._ready_announced = False

        self.discord_identity_service = DiscordIdentityService()
        self.runtime_identity: DiscordRuntimeIdentity | None = None

        self.role_manager = RoleManager()
        self.role_discovery_service = RoleDiscoveryService()
        self.authorization_service = AuthorizationService()
        self.say_service = SayService()
        self.role_classifier = RoleClassifier()
        self.adult_access_classifier = AdultAccessClassifier()

        self.database = DatabaseConnection(
            get_database_path(),
        )

        self.database_ownership_repository = DatabaseOwnershipRepository(
            self.database,
        )

        self.database_ownership_service = DatabaseOwnershipService(
            self.database_ownership_repository,
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
            questionnaire_service=self.member_interest_questionnaire_service,
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

    def _validate_authenticated_bot_identity(self) -> None:
        """Ensure the authenticated Discord bot matches this environment."""

        if self.user is None:
            raise RuntimeError(
                "Discord bot identity is unavailable before command synchronization."
            )

        if self.user.id != self.expected_bot_user_id:
            raise RuntimeError(
                "Authenticated Discord bot identity does not match "
                "configuration. "
                f"Expected DISCORD_BOT_USER_ID={self.expected_bot_user_id}, "
                f"but Discord authenticated user ID {self.user.id}."
            )

    async def _database_is_operational(
        self,
        identity: DiscordRuntimeIdentity,
    ) -> bool:
        """Return whether database-backed commands may be exposed."""

        status = await self.database_status_service.check()

        if status.state != DatabaseState.READY:
            return False

        try:
            await self.database_ownership_service.validate(
                identity.application_id,
            )
        except DatabaseOwnershipUnboundError:
            return False

        return True

    async def request_restart(
        self,
        restart_request: RuntimeRestartRequest,
    ) -> None:
        """Request a clean runtime restart and close the Discord client."""

        logger.info("Redémarrage demandé depuis Discord.")

        self.restart_requested = True
        self.pending_restart_request = restart_request

        logger.info("Fermeture de l'instance courante pour redémarrage...")

        await self.close()

    async def _complete_restart_feedback(self) -> None:
        """Mark the original Discord restart response as completed."""

        restart_request = self.startup_restart_request

        if restart_request is None:
            return

        route = Route(
            "PATCH",
            "/webhooks/{webhook_id}/{webhook_token}/messages/@original",
            webhook_id=restart_request.application_id,
            webhook_token=restart_request.interaction_token,
        )

        await self.http.request(
            route,
            json={
                "content": (
                    "Redémarrage terminé. L'application est de nouveau opérationnelle."
                ),
                "allowed_mentions": {
                    "parse": [],
                },
            },
        )

    def _register_guild_commands(
        self,
        identity: DiscordRuntimeIdentity,
        *,
        database_operational: bool,
    ) -> None:
        """Register commands allowed by the current runtime state."""

        if identity.guild_id != self.guild_id:
            raise RuntimeError(
                "Discord runtime identity belongs to an unexpected guild."
            )

        guild = discord.Object(
            id=self.guild_id,
        )

        self.tree.clear_commands(
            guild=guild,
        )

        self.tree.add_command(
            create_say_command(
                self.authorization_service,
                self.say_service,
                bot_display_name=identity.bot_display_name,
            ),
            guild=guild,
        )

        if database_operational:
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
                self.database_ownership_service,
                self.report_service,
                command_name=identity.admin_command_name,
                application_name=identity.application_name,
                application_id=identity.application_id,
                restart_callback=self.request_restart,
                maintenance_only=not database_operational,
            ),
            guild=guild,
        )

    async def setup_hook(self) -> None:
        if self.started_from_restart:
            logger.info("Redémarrage de l'application en cours...")
        else:
            logger.info("Démarrage de l'application en cours...")

        self._validate_authenticated_bot_identity()

        identity = await self.discord_identity_service.resolve(
            self,
            self.guild_id,
        )

        database_operational = await self._database_is_operational(
            identity,
        )

        self.runtime_identity = identity

        self._register_guild_commands(
            identity,
            database_operational=database_operational,
        )

        guild = discord.Object(
            id=self.guild_id,
        )

        synced = await self.tree.sync(
            guild=guild,
        )

        logger.info(
            "Commandes synchronisées : %s",
            len(synced),
        )

    async def on_ready(self) -> None:
        if self.user is None:
            return

        if self.runtime_identity is None:
            return

        logger.info(
            "%s connecté en tant que %s (%s)",
            self.runtime_identity.application_name,
            self.runtime_identity.bot_display_name,
            self.user.id,
        )

        logger.info(
            "Serveurs accessibles : %s",
            len(self.guilds),
        )

        if self._ready_announced:
            return

        if self.started_from_restart:
            try:
                await self._complete_restart_feedback()

            except Exception:
                logger.exception(
                    "Impossible de mettre à jour le message Discord de redémarrage."
                )

            finally:
                self.startup_restart_request = None

            logger.info("Redémarrage terminé. Application opérationnelle.")

        else:
            logger.info("Démarrage terminé. Application opérationnelle.")

        self._ready_announced = True
