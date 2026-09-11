from unittest.mock import AsyncMock, Mock

import discord

from claviger.commands.claviger_command import create_claviger_group
from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.service import ReportService
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.services.catalog_sync_coordinator_service import (
    CatalogSyncCoordinatorService,
)
from claviger.services.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.guild_policy_bootstrap import (
    GuildPolicyBootstrapService,
)
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import (
    RoleDiscoveryService,
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

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    guild.id = guild_id
    guild.name = guild_name
    guild.owner_id = owner_id

    user = Mock(
        spec=discord.Member,
    )

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
) -> Mock:
    """Create a mocked Discord role for command output tests."""

    role = Mock(
        spec=discord.Role,
    )

    role.name = name
    role.position = position

    return role


def create_test_group(
    role_discovery_service: RoleDiscoveryService,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService | None = None,
    catalog_sync_coordinator_service: CatalogSyncCoordinatorService | None = None,
    catalog_next_coordinator_service: CatalogNextCoordinatorService | None = None,
    database_ownership_service: DatabaseOwnershipService | None = None,
    *,
    command_name: str = "claviger",
    application_name: str = "Claviger",
    application_id: int = 789,
):
    """Create Claviger's command group with mocked external services."""

    policy_resolver = Mock(
        spec=PolicyResolver,
    )

    policy_resolver.resolve = AsyncMock(
        return_value=SUCCUMBRAE_FALLBACK_POLICY,
    )

    database_schema = Mock(
        spec=DatabaseSchema,
    )

    database_schema.initialize = AsyncMock()
    database_schema.migrate = AsyncMock()

    database_status_service = Mock(
        spec=DatabaseStatusService,
    )

    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        )
    )

    report_service = Mock(
        spec=ReportService,
    )

    report_service.emit = AsyncMock()

    if guild_policy_bootstrap_service is None:
        guild_policy_bootstrap_service = Mock(
            spec=GuildPolicyBootstrapService,
        )

        guild_policy_bootstrap_service.bootstrap = AsyncMock()

    if catalog_sync_coordinator_service is None:
        catalog_sync_coordinator_service = Mock(
            spec=CatalogSyncCoordinatorService,
        )

        catalog_sync_coordinator_service.sync = AsyncMock()

    if catalog_next_coordinator_service is None:
        catalog_next_coordinator_service = Mock(
            spec=CatalogNextCoordinatorService,
        )

        catalog_next_coordinator_service.get_next = AsyncMock()
        catalog_next_coordinator_service.update_metadata = AsyncMock()

    if database_ownership_service is None:
        database_ownership_service = Mock(
            spec=DatabaseOwnershipService,
        )

        database_ownership_service.get_owner_application_id = AsyncMock(
            return_value=application_id,
        )

        database_ownership_service.bind = AsyncMock()
        database_ownership_service.validate = AsyncMock()
    role_classifier = RoleClassifier()

    restart_callback = AsyncMock()

    group = create_claviger_group(
        role_discovery_service=role_discovery_service,
        policy_resolver=policy_resolver,
        role_classifier=role_classifier,
        catalog_sync_coordinator_service=catalog_sync_coordinator_service,
        catalog_next_coordinator_service=catalog_next_coordinator_service,
        guild_policy_bootstrap_service=guild_policy_bootstrap_service,
        database_schema=database_schema,
        database_status_service=database_status_service,
        database_ownership_service=database_ownership_service,
        report_service=report_service,
        command_name=command_name,
        application_name=application_name,
        application_id=application_id,
        restart_callback=restart_callback,
    )

    return (
        group,
        policy_resolver,
        database_schema,
        database_status_service,
        report_service,
    )


def get_scan_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger roles scan command."""

    (
        group,
        policy_resolver,
        _,
        _,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    roles_group = group.get_command(
        "roles",
    )

    assert roles_group is not None

    command = roles_group.get_command(
        "scan",
    )

    assert command is not None

    return (
        command,
        policy_resolver,
        report_service,
    )


def get_report_test_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger report test command."""

    (
        group,
        policy_resolver,
        _,
        _,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    report_group = group.get_command(
        "report",
    )

    assert report_group is not None

    command = report_group.get_command(
        "test",
    )

    assert command is not None

    return (
        command,
        policy_resolver,
        report_service,
    )


def get_database_status_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database status command."""

    (
        group,
        _,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "status",
    )

    assert command is not None

    return (
        command,
        database_status_service,
        report_service,
    )


def get_database_initialize_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database initialize command."""

    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "initialize",
    )

    assert command is not None

    return (
        command,
        database_schema,
        database_status_service,
        report_service,
    )


def get_database_migrate_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database migrate command."""

    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "migrate",
    )

    assert command is not None

    return (
        command,
        database_schema,
        database_status_service,
        report_service,
    )


def get_guild_bootstrap_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger guild bootstrap command."""

    bootstrap_service = Mock(
        spec=GuildPolicyBootstrapService,
    )

    bootstrap_service.bootstrap = AsyncMock()

    (
        group,
        _,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        guild_policy_bootstrap_service=bootstrap_service,
    )

    guild_group = group.get_command(
        "guild",
    )

    assert guild_group is not None

    command = guild_group.get_command(
        "bootstrap",
    )

    assert command is not None

    return (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
    )


def get_catalog_sync_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger catalog sync command."""

    catalog_sync_coordinator_service = Mock(
        spec=CatalogSyncCoordinatorService,
    )

    catalog_sync_coordinator_service.sync = AsyncMock()

    (
        group,
        policy_resolver,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        catalog_sync_coordinator_service=catalog_sync_coordinator_service,
    )

    catalog_group = group.get_command(
        "catalog",
    )

    assert catalog_group is not None

    command = catalog_group.get_command(
        "sync",
    )

    assert command is not None

    return (
        command,
        catalog_sync_coordinator_service,
        policy_resolver,
        database_status_service,
        report_service,
    )


def get_catalog_next_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger catalog next command."""

    catalog_next_coordinator_service = Mock(
        spec=CatalogNextCoordinatorService,
    )

    catalog_next_coordinator_service.get_next = AsyncMock()
    catalog_next_coordinator_service.update_metadata = AsyncMock()

    (
        group,
        policy_resolver,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        catalog_next_coordinator_service=catalog_next_coordinator_service,
    )

    catalog_group = group.get_command(
        "catalog",
    )

    assert catalog_group is not None

    command = catalog_group.get_command(
        "next",
    )

    assert command is not None

    return (
        command,
        catalog_next_coordinator_service,
        policy_resolver,
        database_status_service,
        report_service,
    )
