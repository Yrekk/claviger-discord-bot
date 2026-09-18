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
from claviger.commands.admin.claviger_command import create_claviger_group
from claviger.commands.general.say_command import create_say_command

# Config
from claviger.config import (
    get_database_path,
    get_discord_bot_user_id,
    get_discord_guild_id,
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
from claviger.models.runtime.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.runtime.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
from claviger.models.runtime.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
)
from claviger.models.runtime.guild_runtime_state_model import GuildRuntimeState
from claviger.models.runtime.runtime_restart_model import RuntimeRestartRequest

# Policies
from claviger.policies.default_policy import SUCCUMBRAE_FALLBACK_POLICY
from claviger.policies.policy_resolver import PolicyResolver

# Reporting
from claviger.reporting.command_tree import ClavigerCommandTree
from claviger.reporting.discord_bootstrap_dm import DiscordBootstrapDMReporter
from claviger.reporting.discord_forum import DiscordForumReporter
from claviger.reporting.python_logger import PythonLoggingReporter
from claviger.reporting.reporter import Reporter
from claviger.reporting.service import ReportService

# Repositories
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
from claviger.repositories.runtime.database_ownership_repository import (
    DatabaseOwnershipRepository,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)
from claviger.repositories.runtime.guild_policy_repository import GuildPolicyRepository
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)

# Services
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.admin.admin_configuration_reconciliation_service import (
    AdminConfigurationReconciliationService,
)
from claviger.services.admin.admin_structure_discovery_service import (
    AdminStructureDiscoveryService,
)
from claviger.services.admin.admin_structure_provisioning_service import (
    AdminStructureProvisioningService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.authorization import AuthorizationService
from claviger.services.runtime.database_ownership_service import (
    DatabaseOwnershipService,
    DatabaseOwnershipUnboundError,
)
from claviger.services.runtime.discord_identity_service import DiscordIdentityService
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationCoordinatorService,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationService,
)
from claviger.services.runtime.guild_ai_role_provisioning_service import (
    GuildAIRoleProvisioningService,
)
from claviger.services.runtime.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)
from claviger.services.runtime.guild_configuration_readiness_service import (
    GuildConfigurationReadinessService,
)
from claviger.services.runtime.guild_policy_bootstrap import GuildPolicyBootstrapService
from claviger.services.say_service import SayService
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.services.workflows.workflow_configuration_inspection_service import (
    WorkflowConfigurationInspectionService,
)
from claviger.services.workflows.workflow_configuration_reconciliation_service import (
    WorkflowConfigurationReconciliationService,
)
from claviger.services.workflows.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationService,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)
from claviger.services.workflows.workflow_structure_provisioning_service import (
    WorkflowStructureProvisioningService,
)

logger = logging.getLogger(__name__)


class ClavigerBot(discord.Client):
    """Compose and run the Claviger Discord application."""

    def __init__(
        self,
        *,
        startup_restart_request: RuntimeRestartRequest | None = None,
    ) -> None:
        """Compose application-wide and generic guild services."""

        intents = discord.Intents.default()

        super().__init__(
            intents=intents,
        )

        self.tree = ClavigerCommandTree(
            self,
        )

        # Runtime configuration
        self.expected_bot_user_id = get_discord_bot_user_id()

        # Restart state
        self.restart_requested = False
        self.pending_restart_request: RuntimeRestartRequest | None = None
        self.startup_restart_request = startup_restart_request
        self.started_from_restart = startup_restart_request is not None
        self._ready_announced = False

        # Discord identity and application runtime state
        self.discord_identity_service = DiscordIdentityService()
        self.application_identity: DiscordApplicationIdentity | None = None
        self.database_status: DatabaseStatus | None = None
        self.database_operational: bool | None = None

        # Guild runtime state is authoritative per guild.
        self.guild_runtime_states: dict[int, GuildRuntimeState] = {}
        self._guild_configuration_locks: dict[int, Lock] = {}

        # Generic Discord services
        self.role_discovery_service = RoleDiscoveryService()
        self.authorization_service = AuthorizationService()
        self.say_service = SayService()

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

        self.guild_ai_configuration_repository = GuildAIConfigurationRepository(
            self.database,
        )

        self.guild_configuration_metrics_repository = (
            GuildConfigurationMetricsRepository(
                self.database,
            )
        )

        # Guild readiness
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
                provisioning_service=self.admin_structure_provisioning_service,
            )
        )

        # Guild-wide AI configuration pipeline
        self.guild_ai_configuration_service = GuildAIConfigurationService(
            self.guild_ai_configuration_repository,
        )
        self.guild_ai_role_provisioning_service = GuildAIRoleProvisioningService()
        self.guild_ai_configuration_coordinator_service = (
            GuildAIConfigurationCoordinatorService(
                configuration_service=self.guild_ai_configuration_service,
                provisioning_service=self.guild_ai_role_provisioning_service,
            )
        )

        # Generic workflow configuration pipeline
        self.workflow_configuration_repository = WorkflowConfigurationRepository(
            self.database,
        )
        self.workflow_definition_repository = WorkflowDefinitionRepository(
            self.database,
        )
        self.workflow_configuration_inspection_service = (
            WorkflowConfigurationInspectionService(
                workflow_repository=self.workflow_definition_repository,
                ai_repository=self.guild_ai_configuration_repository,
            )
        )
        self.workflow_configuration_validation_service = (
            WorkflowConfigurationValidationService()
        )
        self.workflow_structure_discovery_service = WorkflowStructureDiscoveryService(
            self.role_discovery_service,
        )
        self.workflow_configuration_reconciliation_service = (
            WorkflowConfigurationReconciliationService()
        )
        self.workflow_structure_provisioning_service = (
            WorkflowStructureProvisioningService(
                role_discovery_service=self.role_discovery_service,
                inspection_service=self.workflow_configuration_inspection_service,
            )
        )
        self.workflow_configuration_coordinator_service = (
            WorkflowConfigurationCoordinatorService(
                repository=self.workflow_configuration_repository,
                validation_service=self.workflow_configuration_validation_service,
                discovery_service=self.workflow_structure_discovery_service,
                inspection_service=self.workflow_configuration_inspection_service,
                reconciliation_service=(
                    self.workflow_configuration_reconciliation_service
                ),
                provisioning_service=self.workflow_structure_provisioning_service,
            )
        )

        # Temporary policy compatibility remains only for server inspection and
        # historical bootstrap. It no longer composes specialized workflows.
        policy_fallback_guild_id = get_discord_guild_id()

        self.policy_resolver = PolicyResolver(
            repository=self.guild_policy_repository,
            fallback_guild_id=policy_fallback_guild_id,
        )

        self.guild_policy_bootstrap_service = GuildPolicyBootstrapService(
            repository=self.guild_policy_repository,
            fallback_guild_id=policy_fallback_guild_id,
            bootstrap_policy=SUCCUMBRAE_FALLBACK_POLICY,
        )

        self.guild_configuration_inspection_service = (
            GuildConfigurationInspectionService(
                database_status_service=self.database_status_service,
                database_ownership_service=self.database_ownership_service,
                admin_configuration_coordinator_service=(
                    self.admin_configuration_coordinator_service
                ),
                policy_resolver=self.policy_resolver,
                metrics_repository=self.guild_configuration_metrics_repository,
            )
        )

        # Reporting
        reporters: list[Reporter] = [
            PythonLoggingReporter(),
            DiscordForumReporter(
                client=self,
                repository=self.guild_admin_configuration_repository,
            ),
            DiscordBootstrapDMReporter(
                client=self,
                repository=self.guild_admin_configuration_repository,
            ),
        ]

        self.report_service = ReportService(
            reporters=reporters,
        )

    def _validate_authenticated_bot_identity(self) -> None:
        """Validate that the Discord token belongs to the expected bot."""

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

    async def _database_is_operational(
        self,
        application_identity: DiscordApplicationIdentity,
        status: DatabaseStatus,
    ) -> bool:
        """Return whether database-backed application operations are allowed."""

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
        """Build a deterministic hash of one guild's local command tree."""

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
        """Request a clean in-process runtime restart."""

        logger.info("Redémarrage demandé depuis Discord.")

        self.restart_requested = True

        guild_command_tree_signatures = tuple(
            sorted(
                (
                    guild_id,
                    runtime_state.command_tree_signature,
                )
                for guild_id, runtime_state in self.guild_runtime_states.items()
            )
        )

        self.pending_restart_request = RuntimeRestartRequest(
            application_id=restart_request.application_id,
            interaction_token=restart_request.interaction_token,
            guild_command_tree_signatures=guild_command_tree_signatures,
        )

        logger.info(
            "État restart capturé pour %s serveur(s).",
            len(guild_command_tree_signatures),
        )
        logger.info("Fermeture de l'instance courante pour redémarrage...")

        await self.close()

    async def _complete_restart_feedback(self) -> None:
        """Update the original ephemeral restart interaction after recovery."""

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
        admin_command_channel_id: int | None,
    ) -> None:
        """Build the local Discord command tree for one guild."""

        guild = discord.Object(
            id=guild_identity.guild_id,
        )

        normal_runtime_enabled = database_operational and guild_ready

        self.tree.clear_commands(
            guild=guild,
        )

        # /say is independent from persisted business workflows.
        self.tree.add_command(
            create_say_command(
                self.authorization_service,
                self.say_service,
                bot_display_name=guild_identity.bot_display_name,
            ),
            guild=guild,
        )

        # Specialized /membre and /noctis commands were intentionally removed.
        # Generic runtime workflow commands will be registered from persisted
        # guild_workflows once that runtime layer is implemented.
        self.tree.add_command(
            create_claviger_group(
                self.role_discovery_service,
                self.guild_policy_bootstrap_service,
                self.database_schema,
                self.database_status_service,
                self.database_ownership_service,
                self.report_service,
                admin_configuration_coordinator_service=(
                    self.admin_configuration_coordinator_service
                ),
                ai_configuration_coordinator_service=(
                    self.guild_ai_configuration_coordinator_service
                ),
                workflow_configuration_coordinator_service=(
                    self.workflow_configuration_coordinator_service
                ),
                guild_configuration_inspection_service=(
                    self.guild_configuration_inspection_service
                ),
                command_name=application_identity.admin_command_name,
                application_name=application_identity.application_name,
                application_id=application_identity.application_id,
                database_state=database_status.state,
                database_ownership_bound=database_operational,
                restart_callback=self.request_restart,
                admin_command_channel_id=admin_command_channel_id,
                maintenance_only=not normal_runtime_enabled,
            ),
            guild=guild,
        )

    def _get_guild_configuration_lock(
        self,
        guild_id: int,
    ) -> Lock:
        """Return the synchronization lock dedicated to one Discord guild."""

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
        """Ensure one guild has a current runtime configuration."""

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

            if (
                previous_command_tree_signature is None
                and self.startup_restart_request is not None
            ):
                previous_command_tree_signature = (
                    self.startup_restart_request.command_tree_signature_for(
                        guild_id,
                    )
                )

        return await self._configure_guild(
            application_identity,
            guild_id,
            database_status=database_status,
            database_operational=database_operational,
            previous_command_tree_signature=previous_command_tree_signature,
        )

    async def _configure_guild(
        self,
        application_identity: DiscordApplicationIdentity,
        guild_id: int,
        *,
        database_status: DatabaseStatus,
        database_operational: bool,
        previous_command_tree_signature: str | None = None,
    ) -> GuildRuntimeState:
        """Configure and synchronize runtime state for one Discord guild."""

        configuration_started = perf_counter()

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

        admin_command_channel_id = (
            guild_readiness.configuration.command_channel_id
            if (
                guild_readiness is not None
                and guild_readiness.configuration is not None
            )
            else None
        )

        step_started = perf_counter()

        self._register_guild_commands(
            application_identity,
            guild_identity,
            database_status=database_status,
            database_operational=database_operational,
            guild_ready=guild_ready,
            admin_command_channel_id=admin_command_channel_id,
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

        self.guild_runtime_states[guild_identity.guild_id] = runtime_state

        logger.debug(
            "Timing serveur %s — configuration totale : %.3f s",
            guild_identity.guild_id,
            perf_counter() - configuration_started,
        )

        return runtime_state

    async def setup_hook(self) -> None:
        """Prepare application-wide runtime state before Discord gateway events."""

        setup_started = perf_counter()

        if self.started_from_restart:
            logger.info("Redémarrage de l'application en cours...")
        else:
            logger.info("Démarrage de l'application en cours...")

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

        self.application_identity = application_identity
        self.database_status = database_status
        self.database_operational = database_operational

        logger.debug(
            "Timing startup — validation base / ownership : %.3f s",
            perf_counter() - step_started,
        )
        logger.debug(
            "Timing startup — setup_hook total : %.3f s",
            perf_counter() - setup_started,
        )

    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: app_commands.Command | app_commands.ContextMenu,
    ) -> None:
        """Record one application command that completed without an uncaught error."""

        await self.tree.record_completion(
            interaction,
        )

    async def on_ready(self) -> None:
        """Configure cached guilds and announce a connected runtime."""

        if self.user is None:
            return

        if self.application_identity is None:
            return

        if self.database_status is None:
            return

        if self.database_operational is None:
            return

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
        """Configure a guild joined while the application is already running."""

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
        """Reconfigure a guild that becomes available again."""

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
        """Invalidate runtime state while a guild is unavailable."""

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
        """Forget runtime and local command state for a removed guild."""

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
