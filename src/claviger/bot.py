# Standard library
import hashlib
import json
import logging
from time import perf_counter

# Third-party
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
    DatabaseStatus,
    DatabaseStatusService,
)

# Models
from claviger.models.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
from claviger.models.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
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
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)

# Services
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.admin_configuration_reconciliation_service import (
    AdminConfigurationReconciliationService,
)
from claviger.services.admin_structure_discovery_service import (
    AdminStructureDiscoveryService,
)
from claviger.services.admin_structure_provisioning_service import (
    AdminStructureProvisioningService,
)
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
from claviger.services.guild_configuration_readiness_service import (
    GuildConfigurationReadinessService,
)
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
    """Compose and run the Claviger Discord application.

    The bot owns application-wide services such as the SQLite database and
    Discord application identity, while guild-specific state is resolved
    separately.

    The current runtime still starts from one configured guild ID. The command
    registration API is already guild-independent so that the next migration
    step can register the same application against multiple guilds.
    """

    def __init__(
        self,
        *,
        startup_restart_request: RuntimeRestartRequest | None = None,
    ) -> None:
        """Compose the Discord client and every application service.

        Args:
            startup_restart_request:
                Optional restart context carried from a previous runtime
                instance. When present, Claviger may skip Discord command
                synchronization if the rebuilt tree is unchanged.

        Returns:
            None:
                The bot composition is initialized in memory. No Discord or
                SQLite network/database operation is performed here.
        """

        # Discord client
        intents = discord.Intents.default()

        super().__init__(
            intents=intents,
        )

        self.tree = app_commands.CommandTree(
            self,
        )

        # Legacy runtime configuration
        #
        # These values still anchor the current single-guild startup path.
        # They will disappear when setup_hook becomes fully multi-guild.
        self.guild_id = get_discord_guild_id()
        self.expected_bot_user_id = get_discord_bot_user_id()

        # Restart state
        self.restart_requested = False
        self.pending_restart_request: RuntimeRestartRequest | None = None
        self.command_tree_signature: str | None = None

        self.startup_restart_request = startup_restart_request
        self.started_from_restart = startup_restart_request is not None
        self._ready_announced = False

        # Discord identity state
        self.discord_identity_service = DiscordIdentityService()

        self.application_identity: DiscordApplicationIdentity | None = None
        self.guild_identity: DiscordGuildIdentity | None = None
        self.guild_readiness: GuildConfigurationReadiness | None = None

        # Generic Discord services
        self.role_manager = RoleManager()
        self.role_discovery_service = RoleDiscoveryService()
        self.authorization_service = AuthorizationService()
        self.say_service = SayService()
        self.role_classifier = RoleClassifier()
        self.adult_access_classifier = AdultAccessClassifier()

        # Database infrastructure
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

        # Database ownership
        self.database_ownership_repository = DatabaseOwnershipRepository(
            self.database,
        )

        self.database_ownership_service = DatabaseOwnershipService(
            self.database_ownership_repository,
        )

        # Guild repositories
        self.guild_policy_repository = GuildPolicyRepository(
            self.database,
        )

        self.guild_admin_configuration_repository = GuildAdminConfigurationRepository(
            self.database,
        )

        # Catalog repositories
        self.interest_catalog_repository = InterestCatalogRepository(
            self.database,
        )

        self.access_catalog_repository = AccessCatalogRepository(
            self.database,
        )

        # Guild readiness
        #
        # Application database readiness and guild configuration readiness are
        # intentionally separate concepts. A valid application database may
        # serve several guilds whose configuration states differ.
        self.guild_configuration_readiness_service = GuildConfigurationReadinessService(
            self.guild_admin_configuration_repository,
        )

        # ADMIN configuration pipeline
        self.admin_structure_discovery_service = AdminStructureDiscoveryService()

        self.admin_configuration_reconciliation_service = (
            AdminConfigurationReconciliationService()
        )

        self.admin_structure_provisioning_service = AdminStructureProvisioningService()

        self.admin_configuration_coordinator_service = (
            AdminConfigurationCoordinatorService(
                repository=self.guild_admin_configuration_repository,
                discovery_service=self.admin_structure_discovery_service,
                reconciliation_service=(
                    self.admin_configuration_reconciliation_service
                ),
                provisioning_service=(self.admin_structure_provisioning_service),
            )
        )

        # Member workflow
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

        # Adult / Noctis workflow
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
            questionnaire_service=(self.adult_access_questionnaire_service),
            planner_service=self.noctis_role_planner_service,
            executor_service=self.noctis_role_executor_service,
        )

        # Guild policy
        #
        # The fallback guild is temporary single-guild compatibility. It must
        # disappear before the runtime can be considered fully multi-guild.
        self.policy_resolver = PolicyResolver(
            repository=self.guild_policy_repository,
            fallback_guild_id=self.guild_id,
        )

        self.guild_policy_bootstrap_service = GuildPolicyBootstrapService(
            repository=self.guild_policy_repository,
            fallback_guild_id=self.guild_id,
            bootstrap_policy=SUCCUMBRAE_FALLBACK_POLICY,
        )

        # Catalog synchronization
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

        # Reporting
        reporters: list[Reporter] = [
            PythonLoggingReporter(),
        ]

        # Temporary compatibility:
        # Discord reporting still accepts one environment-provided forum ID.
        # Per-guild DB-backed routing will replace this after multi-guild
        # runtime registration is complete.
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
        """Validate that the Discord token belongs to the expected bot.

        Returns:
            None:
                Authentication is considered valid when the connected Discord
                user matches the configured bot user ID.

        Raises:
            RuntimeError:
                If Discord has not authenticated a bot user yet, or if the
                authenticated bot ID differs from the configured expected ID.
        """

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
        application_identity: DiscordApplicationIdentity,
        status: DatabaseStatus,
    ) -> bool:
        """Check whether database-backed application operations are allowed.

        Args:
            application_identity:
                Discord application identity whose application ID must own the
                SQLite database.

            status:
                Current non-mutating database lifecycle status.

        Returns:
            bool:
                True when the database schema is READY and ownership is bound
                to the current Discord application. False when the database is
                not READY or ownership has not yet been bound.

        Raises:
            DatabaseOwnershipMismatchError:
                Propagated when the database belongs to another Discord
                application. This is a fail-closed condition and must prevent
                command registration.
        """

        if status.state != DatabaseState.READY:
            return False

        try:
            await self.database_ownership_service.validate(
                application_identity.application_id,
            )

        except DatabaseOwnershipUnboundError:
            return False

        return True

    def _build_command_tree_signature(
        self,
        guild: discord.Object,
    ) -> str:
        """Build a deterministic hash of one guild's local command tree.

        Args:
            guild:
                Discord guild object whose locally registered application
                commands must be serialized.

        Returns:
            str:
                SHA-256 hexadecimal digest representing the local command tree.
                Equal signatures mean command synchronization can safely be
                skipped during an internal restart.
        """

        payloads = [
            command.to_dict(
                self.tree,
            )
            for command in self.tree.get_commands(
                guild=guild,
            )
        ]

        payloads.sort(
            key=lambda payload: (
                payload["type"],
                payload["name"],
            )
        )

        serialized = json.dumps(
            payloads,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )

        return hashlib.sha256(
            serialized.encode("utf-8"),
        ).hexdigest()

    async def request_restart(
        self,
        restart_request: RuntimeRestartRequest,
    ) -> None:
        """Request a clean in-process runtime restart.

        Args:
            restart_request:
                Discord interaction context required to resume feedback after
                the new runtime instance starts.

        Returns:
            None:
                Restart state is persisted in memory and the current Discord
                client is closed.

        Side Effects:
            Marks the runtime as restarting and closes the Discord client.
        """

        logger.info("Redémarrage demandé depuis Discord.")

        self.restart_requested = True

        self.pending_restart_request = RuntimeRestartRequest(
            application_id=restart_request.application_id,
            interaction_token=restart_request.interaction_token,
            command_tree_signature=self.command_tree_signature,
        )

        logger.info("Fermeture de l'instance courante pour redémarrage...")

        await self.close()

    async def _complete_restart_feedback(self) -> None:
        """Update the original ephemeral restart interaction after recovery.

        Returns:
            None:
                The method silently returns when no startup restart context is
                available. Otherwise the original Discord response is edited.

        Side Effects:
            Performs one Discord HTTP request when restart context exists.
        """

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
        application_identity: DiscordApplicationIdentity,
        guild_identity: DiscordGuildIdentity,
        *,
        database_status: DatabaseStatus,
        database_operational: bool,
        guild_ready: bool,
    ) -> None:
        """Build the local Discord command tree for one guild.

        Args:
            application_identity:
                Application-wide Discord identity. It supplies the dynamic
                administrative root command name and application ID.

            guild_identity:
                Guild-specific identity. It supplies the target guild ID and
                the bot display name used by guild-facing commands.

            database_status:
                Current application database lifecycle status.

            database_operational:
                True when the application database is READY and owned by the
                authenticated Discord application.

            guild_ready:
                True when this guild has a complete persisted ADMIN
                configuration.

        Returns:
            None:
                Commands are registered only in the local discord.py command
                tree. Discord synchronization happens separately.

        Notes:
            Normal guild workflows require both an operational application
            database and a ready guild configuration.

            Recovery commands remain available when either condition is false.
            This allows a newly joined guild to run ``/{bot} config-server``
            without exposing normal workflows prematurely.
        """

        guild = discord.Object(
            id=guild_identity.guild_id,
        )

        normal_runtime_enabled = database_operational and guild_ready

        self.tree.clear_commands(
            guild=guild,
        )

        # /say remains independent from persistent guild workflows and is
        # available during maintenance/configuration states.
        self.tree.add_command(
            create_say_command(
                self.authorization_service,
                self.say_service,
                bot_display_name=guild_identity.bot_display_name,
            ),
            guild=guild,
        )

        # Business workflows must never be exposed merely because another
        # guild has already configured the shared application database.
        if normal_runtime_enabled:
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

        # The ADMIN root always exists. When the application or guild is not
        # operational, create_claviger_group exposes only recovery/configuration
        # commands such as database, restart and config-server.
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
                admin_configuration_coordinator_service=(
                    self.admin_configuration_coordinator_service
                ),
                command_name=application_identity.admin_command_name,
                application_name=application_identity.application_name,
                application_id=application_identity.application_id,
                database_state=database_status.state,
                database_ownership_bound=database_operational,
                restart_callback=self.request_restart,
                maintenance_only=not normal_runtime_enabled,
            ),
            guild=guild,
        )

    async def setup_hook(self) -> None:
        """Prepare command registration before Discord marks the bot ready.

        Returns:
            None:
                Application identity, database state, current guild identity
                and guild readiness are resolved before the local command tree
                is synchronized.

        Raises:
            RuntimeError:
                If the authenticated Discord identity does not match runtime
                configuration.

            DatabaseOwnershipMismatchError:
                If the SQLite database belongs to another Discord application.

            Database errors:
                Propagated when a database reported as operational cannot be
                queried for guild readiness.

        Notes:
            This method still resolves one configured guild. The command
            registration primitive itself is already guild-independent; the
            following runtime migration will iterate over all accessible guilds.
        """

        setup_started = perf_counter()

        if self.started_from_restart:
            logger.info("Redémarrage de l'application en cours...")
        else:
            logger.info("Démarrage de l'application en cours...")

        # Validate token identity before performing any other startup work.
        step_started = perf_counter()

        self._validate_authenticated_bot_identity()

        logger.debug(
            "Timing startup — validation identité authentifiée : %.3f s",
            perf_counter() - step_started,
        )

        # Resolve application identity independently from guild context.
        step_started = perf_counter()

        application_identity = await self.discord_identity_service.resolve_application(
            self,
        )

        logger.debug(
            "Timing startup — résolution identité application : %.3f s",
            perf_counter() - step_started,
        )

        # Validate the shared application database before any guild-specific
        # persistence is queried.
        step_started = perf_counter()

        database_status = await self.database_status_service.check()

        database_operational = await self._database_is_operational(
            application_identity,
            database_status,
        )

        logger.debug(
            "Timing startup — validation base / ownership : %.3f s",
            perf_counter() - step_started,
        )

        # Resolve guild identity only after application-level safety checks.
        # A database ownership mismatch therefore fails before touching any
        # guild-specific runtime state.
        step_started = perf_counter()

        guild_identity = await self.discord_identity_service.resolve_guild(
            self,
            self.guild_id,
        )

        logger.debug(
            "Timing startup — résolution identité serveur : %.3f s",
            perf_counter() - step_started,
        )

        # Guild readiness is meaningful only when the application database is
        # operational. A missing/unbound database must remain an application
        # maintenance problem instead of becoming a guild configuration error.
        guild_readiness: GuildConfigurationReadiness | None = None

        if database_operational:
            step_started = perf_counter()

            guild_readiness = await self.guild_configuration_readiness_service.inspect(
                guild_identity.guild_id,
            )

            logger.debug(
                "Timing startup — readiness serveur : %.3f s",
                perf_counter() - step_started,
            )

            logger.info(
                "État configuration serveur %s : %s",
                guild_identity.guild_id,
                guild_readiness.state.value,
            )

        guild_ready = guild_readiness.is_ready if guild_readiness is not None else False

        # Store only successfully resolved startup state.
        self.application_identity = application_identity
        self.guild_identity = guild_identity
        self.guild_readiness = guild_readiness

        # Build the command surface appropriate to this guild's state.
        step_started = perf_counter()

        self._register_guild_commands(
            application_identity,
            guild_identity,
            database_status=database_status,
            database_operational=database_operational,
            guild_ready=guild_ready,
        )

        logger.debug(
            "Timing startup — construction arbre local : %.3f s",
            perf_counter() - step_started,
        )

        guild = discord.Object(
            id=guild_identity.guild_id,
        )

        current_signature = self._build_command_tree_signature(
            guild,
        )

        previous_signature = None

        if self.startup_restart_request is not None:
            previous_signature = self.startup_restart_request.command_tree_signature

        tree_is_unchanged = (
            self.started_from_restart
            and previous_signature is not None
            and previous_signature == current_signature
        )

        # Discord command synchronization is expensive and rate-limited enough
        # to justify skipping it when an internal restart rebuilt the exact
        # same command tree.
        step_started = perf_counter()

        if tree_is_unchanged:
            logger.info(
                "Synchronisation Discord ignorée : arbre de commandes inchangé."
            )

        else:
            synced = await self.tree.sync(
                guild=guild,
            )

            logger.info(
                "Commandes synchronisées : %s",
                len(synced),
            )

        logger.debug(
            "Timing startup — synchronisation Discord : %.3f s%s",
            perf_counter() - step_started,
            " (ignorée)" if tree_is_unchanged else "",
        )

        self.command_tree_signature = current_signature

        logger.debug(
            "Timing startup — setup_hook total : %.3f s",
            perf_counter() - setup_started,
        )

    async def on_ready(self) -> None:
        """Announce a successfully connected runtime.

        Returns:
            None:
                The method returns early until both application and guild
                identities are available. Startup logging and restart feedback
                are emitted only once per runtime instance.

        Side Effects:
            May edit the original Discord restart response after a successful
            internal restart.
        """

        if self.user is None:
            return

        if self.application_identity is None:
            return

        if self.guild_identity is None:
            return

        logger.info(
            "%s connecté en tant que %s (%s)",
            self.application_identity.application_name,
            self.guild_identity.bot_display_name,
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
