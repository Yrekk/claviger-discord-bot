from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminStructureDiscoveryResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
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

pytestmark = pytest.mark.asyncio


def _guild() -> MagicMock:
    """Create one deterministic Discord guild."""

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    return guild


def _configuration() -> GuildAdminConfiguration:
    """Create one complete persisted ADMIN routing."""

    return GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )


def _coordinator():
    """Create one coordinator with mocked read and mutation dependencies."""

    repository = MagicMock(
        spec=GuildAdminConfigurationRepository,
    )
    repository.get = AsyncMock()

    discovery_service = MagicMock(
        spec=AdminStructureDiscoveryService,
    )

    reconciliation_service = MagicMock(
        spec=AdminConfigurationReconciliationService,
    )

    provisioning_service = MagicMock(
        spec=AdminStructureProvisioningService,
    )

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
    )


async def test_inspect_reports_ready_when_persisted_routing_matches_discord() -> None:
    """Expose the command channel only when reconciliation can safely KEEP routing."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
    ) = _coordinator()

    guild = _guild()
    configuration = _configuration()
    discovery = AdminStructureDiscoveryResult(
        categories=(),
    )
    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.KEEP,
        category=None,
    )

    repository.get.return_value = configuration
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation

    result = await coordinator.inspect(
        guild,
    )

    repository.get.assert_awaited_once_with(
        123,
    )
    discovery_service.discover.assert_called_once_with(
        guild,
        configured_category_id=100,
    )
    reconciliation_service.reconcile.assert_called_once_with(
        discovery=discovery,
        configuration=configuration,
    )

    assert result.is_routing_ready is True
    assert result.command_channel_id == 200


async def test_inspect_reports_unready_when_discord_drift_requires_repair() -> None:
    """Do not trust persisted routing when Discord resources no longer reconcile."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
    ) = _coordinator()

    guild = _guild()
    configuration = _configuration()
    discovery = AdminStructureDiscoveryResult(
        categories=(),
    )
    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.CREATE,
        category=None,
        issues=("Configured ADMIN category disappeared.",),
    )

    repository.get.return_value = configuration
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation

    result = await coordinator.inspect(
        guild,
    )

    assert result.is_routing_ready is False
    assert result.command_channel_id is None
