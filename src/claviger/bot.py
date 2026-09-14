# Standard library
import hashlib
import json
import logging
from asyncio import Lock
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
from claviger.models.guild_runtime_state_model import GuildRuntimeState
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

        # Discord identity and application runtime state
        self.discord_identity_service = DiscordIdentityService()

        self.application_identity: DiscordApplicationIdentity | None = None
        self.database_status: DatabaseStatus | None = None
        self.database_operational: bool | None = None

        # Temporary compatibility:
        # Legacy single-guild identity/readiness fields remain available while the
        # runtime transitions to event-driven multi-guild configuration.
        self.guild_identity: DiscordGuildIdentity | None = None
        self.guild_readiness: GuildConfigurationReadiness | None = None

        # Guild runtime state is authoritative per guild. Locks prevent overlapping
        # gateway events from configuring and synchronizing the same guild twice.
        self.guild_runtime_states: dict[int, GuildRuntimeState] = {}
        self._guild_configuration_locks: dict[int, Lock] = {}

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

    def _get_guild_configuration_lock(
        self,
        guild_id: int,
    ) -> Lock:
        """Return the synchronization lock dedicated to one Discord guild.

        Args:
            guild_id:
                Discord guild snowflake whose runtime configuration must be
                serialized.

        Returns:
            Lock:
                Stable asynchronous lock shared by every configuration attempt for
                this guild.

        Notes:
            Discord lifecycle events may overlap. Keeping one lock per guild
            prevents duplicate readiness inspection, command-tree mutation and
            Discord synchronization for the same guild.
        """

        lock = self._guild_configuration_locks.get(
            guild_id,
        )

        if lock is None:
            lock = Lock()
            self._guild_configuration_locks[guild_id] = lock

        return lock

    async def _configure_runtime_guild(
        self,
        guild_id: int,
        *,
        force: bool = False,
    ) -> GuildRuntimeState:
        """Ensure one guild has a current runtime configuration.

        Args:
            guild_id:
                Discord guild snowflake to configure.

            force:
                When True, rebuild the guild runtime even when a registered state
                already exists. The existing command-tree signature is preserved
                for synchronization comparison.

        Returns:
            GuildRuntimeState:
                Current successfully configured state for the guild.

        Raises:
            RuntimeError:
                If application-wide startup state is not available yet.

            Database errors:
                Propagated from guild readiness inspection.

            Discord errors:
                Propagated from identity resolution or command synchronization.

        Side Effects:
            May resolve Discord guild identity, inspect persisted readiness,
            rebuild the guild command tree, synchronize commands and replace the
            guild's runtime registry entry.

        Notes:
            The per-guild lock is necessary because ``on_ready``,
            ``on_guild_join`` and ``on_guild_available`` are not guaranteed to run
            in a lifecycle that prevents overlapping work.
        """

        application_identity = self.application_identity
        database_status = self.database_status
        database_operational = self.database_operational

        if (
            application_identity is None
            or database_status is None
            or database_operational is None
        ):
            raise RuntimeError(
                "Application runtime state is unavailable for guild configuration."
            )

        lock = self._get_guild_configuration_lock(
            guild_id,
        )

        async with lock:
            current_state = self.guild_runtime_states.get(
                guild_id,
            )

            if current_state is not None and not force:
                return current_state

            previous_command_tree_signature = (
                current_state.command_tree_signature
                if current_state is not None
                else None
            )

            # Temporary compatibility:
            # The restart model still carries one legacy command-tree signature.
            # Until restart state becomes fully per-guild, apply it only to the
            # configured legacy startup guild.
            if (
                previous_command_tree_signature is None
                and guild_id == self.guild_id
                and self.startup_restart_request is not None
            ):
                previous_command_tree_signature = (
                    self.startup_restart_request.command_tree_signature
                )

            runtime_state = await self._configure_guild(
                application_identity,
                guild_id,
                database_status=database_status,
                database_operational=database_operational,
                previous_command_tree_signature=previous_command_tree_signature,
            )

            # Temporary compatibility:
            # Existing single-guild consumers still read these fields. Only the
            # legacy startup guild mirrors its state here; every guild remains
            # authoritative in guild_runtime_states.
            if guild_id == self.guild_id:
                self.guild_identity = runtime_state.identity
                self.guild_readiness = runtime_state.readiness
                self.command_tree_signature = runtime_state.command_tree_signature

            return runtime_state

    async def _configure_guild(
        self,
        application_identity: DiscordApplicationIdentity,
        guild_id: int,
        *,
        database_status: DatabaseStatus,
        database_operational: bool,
        previous_command_tree_signature: str | None = None,
    ) -> GuildRuntimeState:
        """Configure and synchronize runtime state for one Discord guild.

        Args:
            application_identity:
                Application-wide Discord identity shared by every guild handled by
                this runtime.

            guild_id:
                Discord guild snowflake to configure.

            database_status:
                Current application database lifecycle status.

            database_operational:
                True when the shared application database is READY and owned by the
                authenticated Discord application.

            previous_command_tree_signature:
                Optional command-tree signature previously synchronized for this
                guild. When it matches the rebuilt tree, Discord synchronization is
                skipped.

        Returns:
            GuildRuntimeState:
                Successfully configured guild runtime state, including identity,
                persisted readiness and command-tree signature.

        Raises:
            Database errors:
                Propagated when an operational database cannot provide guild
                readiness.

            Discord errors:
                Propagated when guild identity resolution or command
                synchronization fails.

        Side Effects:
            Rebuilds this guild's local application-command tree, may synchronize
            commands with Discord and replaces this guild's runtime registry entry.

        Notes:
            A guild is stored in ``guild_runtime_states`` only after its runtime
            configuration has completed successfully. A failed reconfiguration
            therefore cannot leave a newly built state marked as operational.
        """

        configuration_started = perf_counter()

        # Fail closed during reconfiguration. An existing snapshot must not remain
        # authoritative while a new configuration attempt is still in progress.
        self.guild_runtime_states.pop(
            guild_id,
            None,
        )

        step_started = perf_counter()

        guild_identity = await self.discord_identity_service.resolve_guild(
            self,
            guild_id,
        )

        logger.debug(
            "Timing serveur %s — résolution identité : %.3f s",
            guild_identity.guild_id,
            perf_counter() - step_started,
        )

        # Guild readiness is meaningful only when the shared application database
        # is operational. Otherwise the guild remains in application maintenance
        # mode rather than being misclassified as unconfigured.
        guild_readiness: GuildConfigurationReadiness | None = None

        if database_operational:
            step_started = perf_counter()

            guild_readiness = await self.guild_configuration_readiness_service.inspect(
                guild_identity.guild_id,
            )

            logger.debug(
                "Timing serveur %s — readiness : %.3f s",
                guild_identity.guild_id,
                perf_counter() - step_started,
            )

            logger.info(
                "État configuration serveur %s : %s",
                guild_identity.guild_id,
                guild_readiness.state.value,
            )

        guild_ready = guild_readiness.is_ready if guild_readiness is not None else False

        step_started = perf_counter()

        self._register_guild_commands(
            application_identity,
            guild_identity,
            database_status=database_status,
            database_operational=database_operational,
            guild_ready=guild_ready,
        )

        logger.debug(
            "Timing serveur %s — construction arbre local : %.3f s",
            guild_identity.guild_id,
            perf_counter() - step_started,
        )

        guild = discord.Object(
            id=guild_identity.guild_id,
        )

        current_signature = self._build_command_tree_signature(
            guild,
        )

        tree_is_unchanged = (
            previous_command_tree_signature is not None
            and previous_command_tree_signature == current_signature
        )

        step_started = perf_counter()

        if tree_is_unchanged:
            logger.info(
                "Synchronisation Discord ignorée pour serveur %s : "
                "arbre de commandes inchangé.",
                guild_identity.guild_id,
            )

        else:
            synced = await self.tree.sync(
                guild=guild,
            )

            logger.info(
                "Commandes synchronisées pour serveur %s : %s",
                guild_identity.guild_id,
                len(synced),
            )

        logger.debug(
            "Timing serveur %s — synchronisation Discord : %.3f s%s",
            guild_identity.guild_id,
            perf_counter() - step_started,
            " (ignorée)" if tree_is_unchanged else "",
        )

        runtime_state = GuildRuntimeState(
            identity=guild_identity,
            readiness=guild_readiness,
            command_tree_signature=current_signature,
        )

        # Only a fully completed configuration attempt becomes authoritative for
        # subsequent runtime operations.
        self.guild_runtime_states[guild_identity.guild_id] = runtime_state

        logger.debug(
            "Timing serveur %s — configuration totale : %.3f s",
            guild_identity.guild_id,
            perf_counter() - configuration_started,
        )

        return runtime_state

    async def setup_hook(self) -> None:
        """Prepare application state and the legacy startup guild.

        Returns:
            None:
                Application identity and database state are resolved once before
                the current legacy guild is delegated to the guild configuration
                routine.

        Raises:
            RuntimeError:
                If the authenticated Discord identity does not match runtime
                configuration.

            DatabaseOwnershipMismatchError:
                If the SQLite database belongs to another Discord application.

            Database errors:
                Propagated when application or guild runtime state cannot be
                resolved safely.

            Discord errors:
                Propagated when guild configuration or command synchronization
                fails.

        Notes:
            This remains a temporary single-guild startup path. Guild-specific
            work is now delegated to ``_configure_guild`` so the next migration
            can invoke the same routine for every accessible guild without
            duplicating runtime behavior.
        """

        setup_started = perf_counter()

        if self.started_from_restart:
            logger.info("Redémarrage de l'application en cours...")
        else:
            logger.info("Démarrage de l'application en cours...")

        # Application-level safety checks must complete before any guild-specific
        # runtime state is inspected or mutated.
        step_started = perf_counter()

        self._validate_authenticated_bot_identity()

        logger.debug(
            "Timing startup — validation identité authentifiée : %.3f s",
            perf_counter() - step_started,
        )

        step_started = perf_counter()

        application_identity = await self.discord_identity_service.resolve_application(
            self,
        )

        logger.debug(
            "Timing startup — résolution identité application : %.3f s",
            perf_counter() - step_started,
        )

        step_started = perf_counter()

        database_status = await self.database_status_service.check()

        database_operational = await self._database_is_operational(
            application_identity,
            database_status,
        )

        # Application-wide state is validated once during startup and then reused by
        # event-driven guild configuration.
        self.application_identity = application_identity
        self.database_status = database_status
        self.database_operational = database_operational

        logger.debug(
            "Timing startup — validation base / ownership : %.3f s",
            perf_counter() - step_started,
        )

        await self._configure_runtime_guild(
            self.guild_id,
            force=True,
        )

        logger.debug(
            "Timing startup — setup_hook total : %.3f s",
            perf_counter() - setup_started,
        )

    async def on_ready(self) -> None:
        """Configure cached guilds and announce a connected runtime.

        Returns:
            None:
                The method returns early until authenticated and application-wide
                runtime state are available.

        Side Effects:
            Ensures every currently available cached guild has runtime state,
            possibly synchronizes guild command trees and may complete restart
            feedback.

        Notes:
            discord.py may dispatch ``on_ready`` more than once. Existing guild
            runtime states are therefore reused rather than rebuilt automatically.
        """

        if self.user is None:
            return

        if self.application_identity is None:
            return

        if self.database_status is None:
            return

        if self.database_operational is None:
            return

        # setup_hook still configures the legacy guild during this migration step.
        # on_ready fills in every other guild now present in Discord's cache.
        for guild in self.guilds:
            if guild.unavailable:
                continue

            try:
                await self._configure_runtime_guild(
                    guild.id,
                )

            except Exception:
                logger.exception(
                    "Impossible de configurer le serveur Discord %s.",
                    guild.id,
                )

        logger.info(
            "%s connectée à Discord (%s)",
            self.application_identity.application_name,
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

    async def on_guild_join(
        self,
        guild: discord.Guild,
    ) -> None:
        """Configure a guild joined while the application is already running.

        Args:
            guild:
                Discord guild newly joined by the authenticated application.

        Returns:
            None:
                Configuration failure is logged and kept isolated from other
                guilds.
        """

        try:
            await self._configure_runtime_guild(
                guild.id,
            )

        except Exception:
            logger.exception(
                "Impossible de configurer le nouveau serveur Discord %s.",
                guild.id,
            )

    async def on_guild_available(
        self,
        guild: discord.Guild,
    ) -> None:
        """Reconfigure a guild that becomes available again.

        Args:
            guild:
                Previously unavailable Discord guild that is accessible again.

        Returns:
            None:
                Configuration failure is logged and kept isolated from other
                guilds.
        """

        try:
            await self._configure_runtime_guild(
                guild.id,
                force=True,
            )

        except Exception:
            logger.exception(
                "Impossible de reconfigurer le serveur Discord %s redevenu disponible.",
                guild.id,
            )

    async def on_guild_unavailable(
        self,
        guild: discord.Guild,
    ) -> None:
        """Invalidate runtime state while a guild is unavailable.

        Args:
            guild:
                Discord guild temporarily marked unavailable.

        Returns:
            None:
                The guild is removed from the authoritative runtime registry.
        """

        lock = self._get_guild_configuration_lock(
            guild.id,
        )

        async with lock:
            self.guild_runtime_states.pop(
                guild.id,
                None,
            )

        logger.warning(
            "Serveur Discord %s indisponible : état runtime invalidé.",
            guild.id,
        )

    async def on_guild_remove(
        self,
        guild: discord.Guild,
    ) -> None:
        """Forget runtime and local command state for a removed guild.

        Args:
            guild:
                Discord guild removed from the authenticated application.

        Returns:
            None:
                Runtime state and locally registered guild commands are discarded.
        """

        lock = self._get_guild_configuration_lock(
            guild.id,
        )

        async with lock:
            self.guild_runtime_states.pop(
                guild.id,
                None,
            )

            self.tree.clear_commands(
                guild=discord.Object(
                    id=guild.id,
                ),
            )

        logger.info(
            "Serveur Discord %s retiré du runtime.",
            guild.id,
        )
