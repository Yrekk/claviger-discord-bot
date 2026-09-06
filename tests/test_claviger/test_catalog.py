from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.models.catalog_sync_model import (
    CatalogSyncEntry,
    CatalogSyncPlan,
)
from claviger.models.catalog_sync_result_model import (
    CatalogSyncCatalogResult,
    CatalogSyncResult,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.role_discovery import (
    RoleDiscoveryService,
)

from .helpers import (
    create_interaction,
    get_catalog_sync_command,
)


@pytest.mark.asyncio
async def test_catalog_sync_synchronizes_all_catalogs() -> None:
    """Synchronize all registered catalogs for the guild owner."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_sync_command(
        role_discovery_service,
    )

    coordinator.sync.return_value = CatalogSyncResult(
        catalogs=(
            CatalogSyncCatalogResult(
                catalog_key="member_interests",
                display_name="Member interests",
                plan=CatalogSyncPlan(
                    creates=(
                        CatalogSyncEntry(
                            role_id=100,
                            role_name="interest-ia",
                            catalog_key="ia",
                            channel_id=200,
                            channel_name="ia",
                            role_manageable=True,
                        ),
                    ),
                    refreshes=(),
                    state_updates=(),
                    warnings=(),
                ),
            ),
            CatalogSyncCatalogResult(
                catalog_key="adult_accesses",
                display_name="Adult accesses",
                plan=CatalogSyncPlan(
                    creates=(),
                    refreshes=(),
                    state_updates=(),
                    warnings=(),
                ),
            ),
        )
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.sync.assert_awaited_once_with(
        interaction.guild,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    report_service.emit.assert_awaited_once()

    message = interaction.followup.send.await_args.args[0]

    assert "Member interests" in message
    assert "Adult accesses" in message
    assert "Total des modifications : 1" in message


@pytest.mark.asyncio
async def test_catalog_sync_rejects_non_owner() -> None:
    """Reject catalog synchronization requested by a non-owner."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_sync_command(
        role_discovery_service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=99,
    )

    await command.callback(
        interaction,
    )

    interaction.response.send_message.assert_awaited_once()

    database_status_service.check.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    coordinator.sync.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_sync_requires_ready_database() -> None:
    """Reject catalog synchronization when the database is not ready."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_sync_command(
        role_discovery_service,
    )

    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=2,
            target_version=4,
        )
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_not_awaited()
    coordinator.sync.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    message = interaction.followup.send.await_args.args[0]

    assert "base de données doit être prête" in message


@pytest.mark.asyncio
async def test_catalog_sync_reports_unexpected_failure() -> None:
    """Report unexpected catalog synchronization failures."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        _,
        report_service,
    ) = get_catalog_sync_command(
        role_discovery_service,
    )

    coordinator.sync.side_effect = RuntimeError(
        "Discord snapshot failed.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.sync.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    message = interaction.followup.send.await_args.args[0]

    assert message == "Échec de la synchronisation des catalogues."
