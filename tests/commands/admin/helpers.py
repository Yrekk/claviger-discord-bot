from unittest.mock import AsyncMock, Mock

import discord

from claviger.commands.admin.claviger_command import create_claviger_group
from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.policies.default_policy import SUCCUMBRAE_FALLBACK_POLICY
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.service import ReportService
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.database_ownership_service import DatabaseOwnershipService
from claviger.services.runtime.guild_policy_bootstrap import GuildPolicyBootstrapService
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)


def create_interaction(
    *,
    owner_id: int = 42,
    user_id: int = 42,
    user_display_name: str = "Yrekk",
    guild_id: int = 123,
    guild_name: str = "Succumbrae Atrium",
) -> Mock:
    """Create a mocked guild interaction for Claviger command tests."""

    interaction = Mock(spec=discord.Interaction)

    guild = Mock(spec=discord.Guild)
    guild.id = guild_id
    guild.name = guild_name
    guild.owner_id = owner_id

    user = Mock(spec=discord.Member)
    user.id = user_id
    user.display_name = user_display_name

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_modal = AsyncMock()

    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    return interaction


def create_role(
    *,
    name: str,
    position: int,
    role_id: int | None = None,
) -> Mock:
    """Create a mocked Discord role for command output tests."""

    role = Mock(spec=discord.Role)
    role.id = position if role_id is None else role_id
    role.name = name
    role.position = position

    return role


def create_test_group(
    role_discovery_service: RoleDiscoveryService,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService | None = None,
    database_ownership_service: DatabaseOwnershipService | None = None,
    admin_configuration_coordinator_service: (
        AdminConfigurationCoordinatorService | None
    ) = None,
    workflow_configuration_coordinator_service: (
        WorkflowConfigurationCoordinatorService | None
    ) = None,
    *,
    command_name: str = "claviger",
    application_name: str = "Claviger",
    application_id: int = 789,
    database_state: DatabaseState = DatabaseState.READY,
    database_ownership_bound: bool = True,
):
    """Create the admin command group with mocked external services."""

    # Kept temporarily for tests that still assert historical policy isolation.
    # It is deliberately not injected into the generic ADMIN composition anymore.
    policy_resolver = Mock(spec=PolicyResolver)
    policy_resolver.resolve = AsyncMock(return_value=SUCCUMBRAE_FALLBACK_POLICY)

    database_schema = Mock(spec=DatabaseSchema)
    database_schema.initialize = AsyncMock()
    database_schema.migrate = AsyncMock()

    database_status_service = Mock(spec=DatabaseStatusService)
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=database_state,
            current_version=(
                2
                if database_state
                not in (
                    DatabaseState.MISSING,
                    DatabaseState.UNINITIALIZED,
                )
                else (0 if database_state == DatabaseState.UNINITIALIZED else None)
            ),
            target_version=2,
        )
    )

    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    if guild_policy_bootstrap_service is None:
        guild_policy_bootstrap_service = Mock(spec=GuildPolicyBootstrapService)
        guild_policy_bootstrap_service.bootstrap = AsyncMock()

    if database_ownership_service is None:
        database_ownership_service = Mock(spec=DatabaseOwnershipService)

        initial_owner_application_id = (
            application_id if database_ownership_bound else None
        )

        database_ownership_service.get_owner_application_id = AsyncMock(
            return_value=initial_owner_application_id,
        )

    async def bind_application(bound_application_id: int) -> None:
        """Simulate the ownership state persisted by the real service."""

        database_ownership_service.get_owner_application_id.return_value = (
            bound_application_id
        )

    database_ownership_service.bind = AsyncMock(side_effect=bind_application)
    database_ownership_service.validate = AsyncMock()

    if admin_configuration_coordinator_service is None:
        admin_configuration_coordinator_service = Mock(
            spec=AdminConfigurationCoordinatorService,
        )
        admin_configuration_coordinator_service.configure = AsyncMock()

    if workflow_configuration_coordinator_service is None:
        workflow_configuration_coordinator_service = Mock(
            spec=WorkflowConfigurationCoordinatorService,
        )
        workflow_configuration_coordinator_service.discover_resources = AsyncMock(
            return_value=WorkflowStructureDiscoveryResult(
                categories=(),
                text_channels=(),
                manageable_roles=(),
                can_create_channels=True,
                can_create_roles=True,
            )
        )
        workflow_configuration_coordinator_service.get_ai_preference_role_id = AsyncMock(
            return_value=None,
        )
        workflow_configuration_coordinator_service.configure = AsyncMock()

    restart_callback = AsyncMock()

    group = create_claviger_group(
        role_discovery_service=role_discovery_service,
        guild_policy_bootstrap_service=guild_policy_bootstrap_service,
        admin_configuration_coordinator_service=admin_configuration_coordinator_service,
        workflow_configuration_coordinator_service=workflow_configuration_coordinator_service,
        database_schema=database_schema,
        database_status_service=database_status_service,
        database_ownership_service=database_ownership_service,
        report_service=report_service,
        command_name=command_name,
        application_name=application_name,
        application_id=application_id,
        database_state=database_state,
        database_ownership_bound=database_ownership_bound,
        restart_callback=restart_callback,
    )

    return (
        group,
        policy_resolver,
        database_schema,
        database_status_service,
        report_service,
    )


def get_scan_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger roles scan command."""

    group, policy_resolver, _, _, report_service = create_test_group(
        role_discovery_service,
    )

    roles_group = group.get_command("roles")
    assert roles_group is not None

    command = roles_group.get_command("scan")
    assert command is not None

    return command, policy_resolver, report_service


def get_report_test_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger report test command."""

    group, policy_resolver, _, _, report_service = create_test_group(
        role_discovery_service,
    )

    report_group = group.get_command("report")
    assert report_group is not None

    command = report_group.get_command("test")
    assert command is not None

    return command, policy_resolver, report_service


def get_database_status_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger database status command."""

    group, _, _, database_status_service, report_service = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command("database")
    assert database_group is not None

    command = database_group.get_command("status")
    assert command is not None

    return command, database_status_service, report_service


def get_database_initialize_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger database initialize command."""

    group, _, database_schema, database_status_service, report_service = (
        create_test_group(
            role_discovery_service,
            database_state=DatabaseState.MISSING,
            database_ownership_bound=False,
        )
    )

    database_group = group.get_command("database")
    assert database_group is not None

    command = database_group.get_command("initialize")
    assert command is not None

    return command, database_schema, database_status_service, report_service


def get_database_migrate_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger database migrate command."""

    group, _, database_schema, database_status_service, report_service = (
        create_test_group(
            role_discovery_service,
            database_state=DatabaseState.MIGRATION_REQUIRED,
            database_ownership_bound=False,
        )
    )

    database_group = group.get_command("database")
    assert database_group is not None

    command = database_group.get_command("migrate")
    assert command is not None

    return command, database_schema, database_status_service, report_service


def get_guild_bootstrap_command(role_discovery_service: RoleDiscoveryService):
    """Create and retrieve the /claviger guild bootstrap command."""

    bootstrap_service = Mock(spec=GuildPolicyBootstrapService)
    bootstrap_service.bootstrap = AsyncMock()

    group, _, _, database_status_service, report_service = create_test_group(
        role_discovery_service,
        guild_policy_bootstrap_service=bootstrap_service,
    )

    guild_group = group.get_command("guild")
    assert guild_group is not None

    command = guild_group.get_command("bootstrap")
    assert command is not None

    return command, bootstrap_service, database_status_service, report_service


def get_config_server_command(
    role_discovery_service: RoleDiscoveryService,
    *,
    database_state: DatabaseState = DatabaseState.READY,
    database_ownership_bound: bool = True,
):
    """Create and retrieve the dynamic /{bot} config-server command."""

    coordinator = Mock(spec=AdminConfigurationCoordinatorService)
    coordinator.configure = AsyncMock()

    group, _, _, _, _ = create_test_group(
        role_discovery_service,
        admin_configuration_coordinator_service=coordinator,
        database_state=database_state,
        database_ownership_bound=database_ownership_bound,
    )

    command = group.get_command("config-server")
    assert command is not None

    return command, coordinator
