from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import DatabaseState, DatabaseStatus
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.ui.admin.admin_configuration_view import AdminConfigurationStartView

from .helpers import create_interaction, create_test_group


def _role_discovery_service() -> Mock:
    """Create one unused role discovery service."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    return service


def _coordinator(
    configuration,
) -> Mock:
    """Create one ADMIN coordinator with deterministic persisted readiness."""

    coordinator = Mock(
        spec=AdminConfigurationCoordinatorService,
    )
    coordinator.configure = AsyncMock()
    coordinator.get_persisted_configuration = AsyncMock(
        return_value=configuration,
    )
    coordinator.discover_candidates = AsyncMock()
    coordinator.prepare_category = AsyncMock()
    coordinator.save_explicit_routing = AsyncMock()

    return coordinator


@pytest.mark.asyncio
async def test_database_migrate_offers_config_server_before_restart_when_admin_missing() -> None:
    """Guide the current guild directly into ADMIN configuration after migration."""

    coordinator = _coordinator(
        None,
    )

    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        _role_discovery_service(),
        admin_configuration_coordinator_service=coordinator,
        database_state=DatabaseState.MIGRATION_REQUIRED,
        database_ownership_bound=False,
        command_name="experimentum",
        application_name="Experimentum",
    )

    database_group = group.get_command(
        "database",
    )
    assert database_group is not None

    command = database_group.get_command(
        "migrate",
    )
    assert command is not None

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=8,
            target_version=9,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=9,
            target_version=9,
        ),
    ]

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_awaited_once()
    coordinator.get_persisted_configuration.assert_awaited_once_with(
        interaction.guild.id,
    )

    first_send = interaction.followup.send.await_args_list[0]
    message = first_send.args[0]
    view = first_send.kwargs["view"]

    assert "`8` → `9`" in message
    assert "configuration ADMIN" in message
    assert isinstance(
        view,
        AdminConfigurationStartView,
    )
    assert "/experimentum restart" not in message

    report_service.emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_database_migrate_keeps_normal_restart_guidance_when_admin_ready() -> None:
    """Skip the bootstrap button when persisted ADMIN routing is already complete."""

    complete_configuration = Mock(
        is_complete=True,
    )
    coordinator = _coordinator(
        complete_configuration,
    )

    (
        group,
        _,
        database_schema,
        database_status_service,
        _,
    ) = create_test_group(
        _role_discovery_service(),
        admin_configuration_coordinator_service=coordinator,
        database_state=DatabaseState.MIGRATION_REQUIRED,
        database_ownership_bound=False,
        command_name="experimentum",
        application_name="Experimentum",
    )

    database_group = group.get_command(
        "database",
    )
    assert database_group is not None

    command = database_group.get_command(
        "migrate",
    )
    assert command is not None

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=8,
            target_version=9,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=9,
            target_version=9,
        ),
    ]

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_awaited_once()

    first_send = interaction.followup.send.await_args_list[0]

    assert "/experimentum restart" in first_send.args[0]
    assert "view" not in first_send.kwargs


@pytest.mark.asyncio
async def test_database_bind_offers_config_server_before_restart_when_admin_missing() -> None:
    """Guide an unbound ready database into guild ADMIN configuration before restart."""

    coordinator = _coordinator(
        None,
    )

    (
        group,
        _,
        _,
        database_status_service,
        _,
    ) = create_test_group(
        _role_discovery_service(),
        admin_configuration_coordinator_service=coordinator,
        database_state=DatabaseState.READY,
        database_ownership_bound=False,
        command_name="experimentum",
        application_name="Experimentum",
    )

    database_group = group.get_command(
        "database",
    )
    assert database_group is not None

    command = database_group.get_command(
        "bind",
    )
    assert command is not None

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.READY,
        current_version=9,
        target_version=9,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    first_send = interaction.followup.send.await_args_list[0]

    assert "configuration ADMIN" in first_send.args[0]
    assert "/experimentum restart" not in first_send.args[0]
    assert isinstance(
        first_send.kwargs["view"],
        AdminConfigurationStartView,
    )
