from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.repositories.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.services.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.services.workflow_configuration_reconciliation_service import (
    WorkflowConfigurationReconciliationService,
)
from claviger.services.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationService,
)
from claviger.services.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)
from claviger.services.workflow_structure_provisioning_service import (
    WorkflowStructureProvisioningService,
)

pytestmark = pytest.mark.asyncio


def _service() -> tuple[
    WorkflowConfigurationCoordinatorService,
    MagicMock,
    MagicMock,
]:
    """Create one coordinator with mocked read-side dependencies."""

    repository = MagicMock(
        spec=WorkflowConfigurationRepository,
    )
    repository.get_ai_preference_role_id = AsyncMock(
        return_value=301,
    )

    discovery_service = MagicMock(
        spec=WorkflowStructureDiscoveryService,
    )

    discovery_service.discover = AsyncMock(
        return_value=WorkflowStructureDiscoveryResult(
            categories=(),
            text_channels=(),
            manageable_roles=(),
            can_create_channels=True,
            can_create_roles=True,
        )
    )

    service = WorkflowConfigurationCoordinatorService(
        repository=repository,
        validation_service=MagicMock(
            spec=WorkflowConfigurationValidationService,
        ),
        discovery_service=discovery_service,
        reconciliation_service=MagicMock(
            spec=WorkflowConfigurationReconciliationService,
        ),
        provisioning_service=MagicMock(
            spec=WorkflowStructureProvisioningService,
        ),
    )

    return (
        service,
        repository,
        discovery_service,
    )


async def test_discover_resources_delegates_to_authoritative_discovery() -> None:
    """Expose discovery to frontends without duplicating Discord logic."""

    service, _, discovery_service = _service()

    guild = MagicMock(
        spec=discord.Guild,
    )

    result = await service.discover_resources(
        guild,
    )

    discovery_service.discover.assert_awaited_once_with(
        guild,
    )

    assert result.can_create_channels is True
    assert result.can_create_roles is True


async def test_get_ai_preference_role_id_delegates_to_repository() -> None:
    """Expose the shared persisted AI role through the coordinator boundary."""

    service, repository, _ = _service()

    role_id = await service.get_ai_preference_role_id(
        123,
    )

    repository.get_ai_preference_role_id.assert_awaited_once_with(
        123,
    )

    assert role_id == 301
