from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminStructureDiscoveryResult,
)
from claviger.models.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
)
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
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

pytestmark = pytest.mark.asyncio


def _guild() -> MagicMock:
    """Create one deterministic Discord guild."""

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    return guild


def _channel(
    *,
    channel_id: int,
    name: str,
    channel_type: str,
    usable: bool = True,
) -> AdminChannelCandidate:
    """Create one ADMIN channel candidate."""

    return AdminChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        channel_type=channel_type,
        everyone_can_view=False,
        bot_can_view=usable,
        bot_can_send=usable,
    )


def _ready_category() -> AdminCategoryCandidate:
    """Create one complete usable ADMIN category."""

    return AdminCategoryCandidate(
        category_id=100,
        category_name="Claviger Admin",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(
            _channel(
                channel_id=200,
                name="admin-commands",
                channel_type="text",
            ),
            _channel(
                channel_id=201,
                name="report-activity",
                channel_type="forum",
            ),
            _channel(
                channel_id=202,
                name="report-error",
                channel_type="forum",
            ),
        ),
    )


def _incomplete_category() -> AdminCategoryCandidate:
    """Create one selected category that needs safe structural completion."""

    return AdminCategoryCandidate(
        category_id=100,
        category_name="Claviger Admin",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(
            _channel(
                channel_id=200,
                name="admin-commands",
                channel_type="text",
            ),
        ),
    )


def _services():
    """Create one coordinator with mocked persistence and Discord services."""

    repository = MagicMock(
        spec=GuildAdminConfigurationRepository,
    )
    repository.get = AsyncMock()
    repository.save = AsyncMock()

    discovery_service = MagicMock(
        spec=AdminStructureDiscoveryService,
    )

    reconciliation_service = MagicMock(
        spec=AdminConfigurationReconciliationService,
    )

    provisioning_service = MagicMock(
        spec=AdminStructureProvisioningService,
    )
    provisioning_service.provision = AsyncMock()

    coordinator = AdminConfigurationCoordinatorService(
        repository=repository,
        discovery_service=discovery_service,
        reconciliation_service=reconciliation_service,
        provisioning_service=provisioning_service,
    )

    return (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    )


async def test_prepare_category_completes_only_explicit_selection() -> None:
    """Repair one human-selected category before exposing routing choices."""

    (
        coordinator,
        _,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()
    incomplete = _incomplete_category()
    ready = _ready_category()

    discovery_service.discover.side_effect = [
        AdminStructureDiscoveryResult(
            categories=(incomplete,),
        ),
        AdminStructureDiscoveryResult(
            categories=(ready,),
        ),
    ]

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.COMPLETE,
        category=incomplete,
        issues=("At least two forums are required.",),
    )
    reconciliation_service.reconcile.return_value = reconciliation

    provisioning_service.provision.return_value = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.COMPLETE,
        category_id=100,
        created_channel_ids=(201, 202),
    )

    result = await coordinator.prepare_category(
        guild,
        100,
    )

    provisioning_service.provision.assert_awaited_once_with(
        guild=guild,
        reconciliation=reconciliation,
        configuration=None,
    )

    assert result == ready
    assert result.is_structurally_ready is True


async def test_save_explicit_routing_persists_only_current_usable_channels() -> None:
    """Persist a human routing choice only after fresh Discord validation."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()
    category = _ready_category()

    discovery_service.discover.return_value = AdminStructureDiscoveryResult(
        categories=(category,),
    )
    reconciliation_service.reconcile.return_value = (
        AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.IMPORT,
            category=category,
        )
    )

    configuration = await coordinator.save_explicit_routing(
        guild,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    provisioning_service.provision.assert_not_awaited()
    repository.save.assert_awaited_once_with(
        configuration,
    )

    assert configuration.guild_id == 123
    assert configuration.category_id == 100
    assert configuration.command_channel_id == 200
    assert configuration.activity_forum_id == 201
    assert configuration.error_forum_id == 202


async def test_save_explicit_routing_rejects_channel_outside_selected_category() -> None:
    """Never persist a routing destination outside the selected ADMIN category."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        _,
    ) = _services()

    guild = _guild()
    category = _ready_category()

    discovery_service.discover.return_value = AdminStructureDiscoveryResult(
        categories=(category,),
    )
    reconciliation_service.reconcile.return_value = (
        AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.IMPORT,
            category=category,
        )
    )

    with pytest.raises(
        ValueError,
        match="administrative command channel",
    ):
        await coordinator.save_explicit_routing(
            guild,
            category_id=100,
            command_channel_id=999,
            activity_forum_id=201,
            error_forum_id=202,
        )

    repository.save.assert_not_awaited()


async def test_save_explicit_routing_rejects_same_activity_and_error_forum() -> None:
    """Require distinct semantic destinations even when one forum is usable."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        _,
    ) = _services()

    guild = _guild()
    category = _ready_category()

    discovery_service.discover.return_value = AdminStructureDiscoveryResult(
        categories=(category,),
    )
    reconciliation_service.reconcile.return_value = (
        AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.IMPORT,
            category=category,
        )
    )

    with pytest.raises(
        ValueError,
        match="Activity and error forums must be different",
    ):
        await coordinator.save_explicit_routing(
            guild,
            category_id=100,
            command_channel_id=200,
            activity_forum_id=201,
            error_forum_id=201,
        )

    repository.save.assert_not_awaited()
