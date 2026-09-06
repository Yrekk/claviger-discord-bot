from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.models.catalog_next_selection_model import (
    CatalogNextSelection,
)
from claviger.models.catalog_sync_model import (
    CatalogSyncEntry,
    CatalogSyncPlan,
)
from claviger.models.catalog_sync_result_model import (
    CatalogSyncCatalogResult,
    CatalogSyncResult,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.role_discovery import (
    RoleDiscoveryService,
)
from claviger.ui.catalog_metadata_modal import (
    CatalogMetadataModal,
)

from .helpers import (
    create_interaction,
    get_catalog_next_command,
    get_catalog_sync_command,
)


def create_next_selection() -> CatalogNextSelection:
    """Create an incomplete catalog entry for command tests."""

    entry = RoleChannelCatalogEntry(
        guild_id=123,
        role_id=100,
        role_name="interest-ludus",
        catalog_key="ludus",
        channel_id=200,
        channel_name="ludus",
        label=None,
        description=None,
        emoji=None,
        sort_order=0,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )

    return CatalogNextSelection(
        catalog_key="member_interests",
        display_name="Member interests",
        entry_name="Member interest",
        entry=entry,
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


@pytest.mark.asyncio
async def test_catalog_next_opens_metadata_modal() -> None:
    """Open the metadata modal for the next incomplete entry."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_next_command(
        role_discovery_service,
    )

    coordinator.get_next.return_value = create_next_selection()

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.get_next.assert_awaited_once_with(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    report_service.emit.assert_not_awaited()

    modal = interaction.response.send_modal.await_args.args[0]

    assert isinstance(
        modal,
        CatalogMetadataModal,
    )


@pytest.mark.asyncio
async def test_catalog_next_reports_completion() -> None:
    """Report when every catalog entry is already configured."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        _,
        _,
        report_service,
    ) = get_catalog_next_command(
        role_discovery_service,
    )

    coordinator.get_next.return_value = None

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    message = interaction.response.send_message.await_args.args[0]

    assert "Tous les catalogues disponibles sont configurés" in message

    interaction.response.send_modal.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_next_rejects_non_owner() -> None:
    """Reject catalog configuration requested by a non-owner."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_next_command(
        role_discovery_service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=99,
    )

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    coordinator.get_next.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_catalog_next_requires_ready_database() -> None:
    """Reject catalog configuration while the database is not ready."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_catalog_next_command(
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
    coordinator.get_next.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_modal.assert_not_awaited()


@pytest.mark.asyncio
async def test_catalog_next_reports_unexpected_failure() -> None:
    """Report unexpected failures while selecting the next entry."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        _,
        report_service,
    ) = get_catalog_next_command(
        role_discovery_service,
    )

    coordinator.get_next.side_effect = RuntimeError(
        "Unable to read catalog.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.get_next.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    interaction.response.send_modal.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert message == ("Impossible de déterminer la prochaine entrée à configurer.")
