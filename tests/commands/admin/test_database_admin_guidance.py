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
    )

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=1,
            target_version=2,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        ),
    ]

    command = group.get_command("database").get_command("migrate")
    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_awaited_once()
    coordinator.get_persisted_configuration.assert_awaited_once_with(
        interaction.guild.id,
    )
    report_service.emit.assert_awaited_once()

    call_args = interaction.followup.send.await_args
    assert "config-server" in call_args.args[0]
    assert isinstance(
        call_args.kwargs["view"],
        AdminConfigurationStartView,
    )


@pytest.mark.asyncio
async def test_database_migrate_reports_ready_admin_configuration() -> None:
    """Report readiness immediately when ADMIN configuration already exists."""

    configuration = Mock()
    coordinator = _coordinator(
        configuration,
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
    )

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=1,
            target_version=2,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        ),
    ]

    command = group.get_command("database").get_command("migrate")
    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_awaited_once()
    coordinator.get_persisted_configuration.assert_awaited_once_with(
        interaction.guild.id,
    )
    report_service.emit.assert_awaited_once()

    call_args = interaction.followup.send.await_args
    assert "Configuration ADMIN déjà prête" in call_args.args[0]
    assert "restart" in call_args.args[0]
    assert "view" not in call_args.kwargs
