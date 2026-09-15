from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
from claviger.models.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowConfigurationSpec,
    WorkflowResourceSelection,
)
from claviger.models.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.models.workflow_structure_provisioning_model import (
    WorkflowStructureProvisioningResult,
)
from claviger.repositories.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.services.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
    WorkflowConfigurationPersistenceAfterProvisioningError,
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


def _existing(
    resource_id: int,
) -> WorkflowResourceSelection:
    """Create one deterministic existing-resource selection."""

    return WorkflowResourceSelection(
        mode="existing",
        resource_id=resource_id,
    )


def _spec() -> WorkflowConfigurationSpec:
    """Create one normalized workflow configuration."""

    return WorkflowConfigurationSpec(
        guild_id=123,
        workflow_key="member",
        title="Membre",
        description=None,
        command_name="membre",
        command_description="Gère ton profil membre.",
        category=_existing(
            100,
        ),
        management_channel=_existing(
            200,
        ),
        execution_channel=_existing(
            201,
        ),
        primary_role=_existing(
            300,
        ),
        questionnaire_role_prefix="interest-",
        ai_enabled=True,
        ai_preference_role=_existing(
            301,
        ),
    )


def _resolved() -> ResolvedWorkflowConfiguration:
    """Create one final persisted workflow configuration."""

    return ResolvedWorkflowConfiguration(
        guild_id=123,
        workflow_key="member",
        title="Membre",
        description=None,
        command_name="membre",
        command_description="Gère ton profil membre.",
        category_id=100,
        management_channel_id=200,
        execution_channel_id=201,
        primary_role_id=300,
        questionnaire_role_prefix="interest-",
        ai_preference_role_id=301,
    )


def _discovery() -> WorkflowStructureDiscoveryResult:
    """Create one minimal discovery object handled by mocked reconciliation."""

    return WorkflowStructureDiscoveryResult(
        categories=(),
        text_channels=(),
        manageable_roles=(),
        can_create_channels=True,
        can_create_roles=True,
    )


async def test_configure_runs_complete_workflow_pipeline() -> None:
    """Coordinate validation through final SQLite persistence."""

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    draft = MagicMock(
        spec=WorkflowConfigurationDraft,
    )
    draft.guild_id = 123

    validated = _spec()
    reconciled = _spec()

    discovery = _discovery()

    provisioning = WorkflowStructureProvisioningResult(
        guild_id=123,
        configuration=_resolved(),
    )

    repository = MagicMock(
        spec=WorkflowConfigurationRepository,
    )
    repository.get_ai_preference_role_id = AsyncMock(
        return_value=301,
    )
    repository.save = AsyncMock()

    validation_service = MagicMock(
        spec=WorkflowConfigurationValidationService,
    )
    validation_service.validate.return_value = validated

    discovery_service = MagicMock(
        spec=WorkflowStructureDiscoveryService,
    )
    discovery_service.discover = AsyncMock(
        return_value=discovery,
    )

    reconciliation_service = MagicMock(
        spec=WorkflowConfigurationReconciliationService,
    )
    reconciliation_service.reconcile.return_value = reconciled

    provisioning_service = MagicMock(
        spec=WorkflowStructureProvisioningService,
    )
    provisioning_service.provision = AsyncMock(
        return_value=provisioning,
    )

    service = WorkflowConfigurationCoordinatorService(
        repository=repository,
        validation_service=validation_service,
        discovery_service=discovery_service,
        reconciliation_service=reconciliation_service,
        provisioning_service=provisioning_service,
    )

    result = await service.configure(
        guild=guild,
        draft=draft,
    )

    assert result is provisioning

    validation_service.validate.assert_called_once_with(
        draft,
    )

    discovery_service.discover.assert_awaited_once_with(
        guild,
    )

    repository.get_ai_preference_role_id.assert_awaited_once_with(
        123,
    )

    reconciliation_service.reconcile.assert_called_once_with(
        configuration=validated,
        discovery=discovery,
        persisted_ai_preference_role_id=301,
    )

    provisioning_service.provision.assert_awaited_once_with(
        guild=guild,
        configuration=reconciled,
    )

    repository.save.assert_awaited_once_with(
        provisioning.configuration,
    )


async def test_configure_reports_persistence_failure_after_provisioning() -> None:
    """Preserve provisioning details when SQLite persistence later fails."""

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    draft = MagicMock(
        spec=WorkflowConfigurationDraft,
    )
    draft.guild_id = 123

    configuration = _spec()

    provisioning = WorkflowStructureProvisioningResult(
        guild_id=123,
        configuration=_resolved(),
        created_category_id=100,
        created_channel_ids=(
            200,
            201,
        ),
        created_role_ids=(
            300,
            301,
        ),
    )

    repository = MagicMock(
        spec=WorkflowConfigurationRepository,
    )
    repository.get_ai_preference_role_id = AsyncMock(
        return_value=301,
    )
    repository.save = AsyncMock(
        side_effect=RuntimeError(
            "SQLite failure.",
        ),
    )

    validation_service = MagicMock(
        spec=WorkflowConfigurationValidationService,
    )
    validation_service.validate.return_value = configuration

    discovery_service = MagicMock(
        spec=WorkflowStructureDiscoveryService,
    )
    discovery_service.discover = AsyncMock(
        return_value=_discovery(),
    )

    reconciliation_service = MagicMock(
        spec=WorkflowConfigurationReconciliationService,
    )
    reconciliation_service.reconcile.return_value = configuration

    provisioning_service = MagicMock(
        spec=WorkflowStructureProvisioningService,
    )
    provisioning_service.provision = AsyncMock(
        return_value=provisioning,
    )

    service = WorkflowConfigurationCoordinatorService(
        repository=repository,
        validation_service=validation_service,
        discovery_service=discovery_service,
        reconciliation_service=reconciliation_service,
        provisioning_service=provisioning_service,
    )

    with pytest.raises(
        WorkflowConfigurationPersistenceAfterProvisioningError,
    ) as captured:
        await service.configure(
            guild=guild,
            draft=draft,
        )

    assert captured.value.provisioning is provisioning
