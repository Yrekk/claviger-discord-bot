from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminStructureDiscoveryResult,
)
from claviger.models.admin.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
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


def _configuration(
    *,
    category_id: int = 100,
    command_channel_id: int | None = 200,
    activity_forum_id: int = 201,
    error_forum_id: int | None = 202,
) -> GuildAdminConfiguration:
    """Create one deterministic persisted ADMIN configuration."""

    return GuildAdminConfiguration(
        guild_id=123,
        category_id=category_id,
        command_channel_id=command_channel_id,
        activity_forum_id=activity_forum_id,
        error_forum_id=error_forum_id,
    )


def _category(
    *,
    category_id: int = 100,
) -> AdminCategoryCandidate:
    """Create one deterministic discovered ADMIN category."""

    return AdminCategoryCandidate(
        category_id=category_id,
        category_name="Claviger Admin",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(),
    )


def _services():
    """Create mocked ADMIN coordination dependencies."""

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


async def test_create_persists_newly_provisioned_configuration() -> None:
    """Persist deterministic routing created entirely by Claviger."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()

    discovery = AdminStructureDiscoveryResult(
        categories=(),
    )

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.CREATE,
        category=None,
    )

    created_configuration = _configuration()

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.CREATE,
        category_id=100,
        created_category=True,
        created_channel_ids=(
            200,
            201,
            202,
        ),
        configuration=created_configuration,
    )

    repository.get.return_value = None
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation
    provisioning_service.provision.return_value = provisioning

    result = await coordinator.configure(
        guild,
    )

    repository.get.assert_awaited_once_with(
        123,
    )

    discovery_service.discover.assert_called_once_with(
        guild,
        configured_category_id=None,
    )

    reconciliation_service.reconcile.assert_called_once_with(
        discovery=discovery,
        configuration=None,
    )

    provisioning_service.provision.assert_awaited_once_with(
        guild=guild,
        reconciliation=reconciliation,
        configuration=None,
    )

    repository.save.assert_awaited_once_with(
        created_configuration,
    )

    assert result.configuration_before is None
    assert result.configuration_after == created_configuration
    assert result.configuration_updated is True


async def test_keep_uses_persisted_category_identity_without_rewriting() -> None:
    """Validate configured Discord identity without performing a redundant DB save."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()
    configuration = _configuration()

    category = _category()

    discovery = AdminStructureDiscoveryResult(
        categories=(category,),
    )

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.KEEP,
        category=category,
    )

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.KEEP,
        category_id=100,
        configuration=configuration,
    )

    repository.get.return_value = configuration
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation
    provisioning_service.provision.return_value = provisioning

    result = await coordinator.configure(
        guild,
    )

    discovery_service.discover.assert_called_once_with(
        guild,
        configured_category_id=100,
    )

    repository.save.assert_not_awaited()

    assert result.configuration_before == configuration
    assert result.configuration_after == configuration
    assert result.configuration_updated is False


async def test_complete_persists_repaired_routing() -> None:
    """Persist new Discord identities when provisioning repairs missing routing."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()

    configuration_before = _configuration(
        error_forum_id=None,
    )

    configuration_after = _configuration(
        error_forum_id=203,
    )

    category = _category()

    discovery = AdminStructureDiscoveryResult(
        categories=(category,),
    )

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.COMPLETE,
        category=category,
        issues=("No error report forum is configured.",),
    )

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.COMPLETE,
        category_id=100,
        created_channel_ids=(203,),
        configuration=configuration_after,
    )

    repository.get.return_value = configuration_before
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation
    provisioning_service.provision.return_value = provisioning

    result = await coordinator.configure(
        guild,
    )

    repository.save.assert_awaited_once_with(
        configuration_after,
    )

    assert result.configuration_before == configuration_before
    assert result.configuration_after == configuration_after
    assert result.configuration_updated is True


async def test_import_without_semantic_mapping_does_not_persist() -> None:
    """Never infer activity/error routing from an existing Discord shape."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()
    category = _category()

    discovery = AdminStructureDiscoveryResult(
        categories=(category,),
    )

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.IMPORT,
        category=category,
    )

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.IMPORT,
        category_id=100,
        configuration=None,
    )

    repository.get.return_value = None
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation
    provisioning_service.provision.return_value = provisioning

    result = await coordinator.configure(
        guild,
    )

    repository.save.assert_not_awaited()

    assert result.configuration_before is None
    assert result.configuration_after is None
    assert result.configuration_updated is False


async def test_needs_choice_preserves_existing_configuration_without_write() -> None:
    """Keep stale persisted state visible while refusing an ambiguous replacement."""

    (
        coordinator,
        repository,
        discovery_service,
        reconciliation_service,
        provisioning_service,
    ) = _services()

    guild = _guild()

    configuration = _configuration(
        category_id=100,
    )

    alternative = _category(
        category_id=999,
    )

    discovery = AdminStructureDiscoveryResult(
        categories=(alternative,),
    )

    reconciliation = AdminConfigurationReconciliationResult(
        decision=AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
        category=None,
        issues=("Configured ADMIN category disappeared.",),
    )

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
        category_id=None,
        configuration=None,
    )

    repository.get.return_value = configuration
    discovery_service.discover.return_value = discovery
    reconciliation_service.reconcile.return_value = reconciliation
    provisioning_service.provision.return_value = provisioning

    result = await coordinator.configure(
        guild,
    )

    repository.save.assert_not_awaited()

    assert result.configuration_before == configuration
    assert result.configuration_after == configuration
    assert result.configuration_updated is False
