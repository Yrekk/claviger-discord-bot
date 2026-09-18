from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflows.workflow_configuration_inspection_model import (
    WorkflowConfigurationInspection,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.services.workflows.workflow_configuration_inspection_service import (
    WorkflowConfigurationInspectionService,
)
from claviger.services.workflows.workflow_configuration_reconciliation_service import (
    WorkflowConfigurationReconciliationService,
)
from claviger.services.workflows.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationService,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)
from claviger.services.workflows.workflow_structure_provisioning_service import (
    WorkflowStructureProvisioningService,
)

pytestmark = pytest.mark.asyncio


def _empty_inspection() -> WorkflowConfigurationInspection:
    """Return one V11 inspection without existing reservations."""

    return WorkflowConfigurationInspection(
        guild_id=123,
        workflows=(),
        ai_role_id=None,
        reserved_role_ids=frozenset(),
        reserved_role_prefixes=(),
    )


def _service(
    discovery: WorkflowStructureDiscoveryResult,
    inspection: WorkflowConfigurationInspection | None = None,
) -> tuple[
    WorkflowConfigurationCoordinatorService,
    MagicMock,
    MagicMock,
]:
    """Create one coordinator with mocked read-side dependencies."""

    repository = MagicMock(
        spec=WorkflowConfigurationRepository,
    )
    discovery_service = MagicMock(
        spec=WorkflowStructureDiscoveryService,
    )
    discovery_service.discover = AsyncMock(
        return_value=discovery,
    )

    inspection_service = MagicMock(
        spec=WorkflowConfigurationInspectionService,
    )
    inspection_service.inspect = AsyncMock(
        return_value=inspection or _empty_inspection(),
    )
    inspection_service.is_role_reserved.side_effect = (
        WorkflowConfigurationInspectionService.is_role_reserved
    )

    service = WorkflowConfigurationCoordinatorService(
        repository=repository,
        validation_service=MagicMock(
            spec=WorkflowConfigurationValidationService,
        ),
        discovery_service=discovery_service,
        inspection_service=inspection_service,
        reconciliation_service=MagicMock(
            spec=WorkflowConfigurationReconciliationService,
        ),
        provisioning_service=MagicMock(
            spec=WorkflowStructureProvisioningService,
        ),
    )

    return (
        service,
        discovery_service,
        inspection_service,
    )


async def test_discover_resources_delegates_to_authoritative_sources() -> None:
    """Combine Discord discovery with persisted V11 inspection."""

    discovery = WorkflowStructureDiscoveryResult(
        categories=(),
        text_channels=(),
        manageable_roles=(),
        can_create_channels=True,
        can_create_roles=True,
    )
    service, discovery_service, inspection_service = _service(
        discovery,
    )

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    result = await service.discover_resources(
        guild,
    )

    discovery_service.discover.assert_awaited_once_with(
        guild,
    )
    inspection_service.inspect.assert_awaited_once_with(
        123,
        current_workflow_key=None,
    )

    assert result.can_create_channels is True
    assert result.can_create_roles is True


async def test_discover_resources_filters_reserved_roles_and_annotates_structure() -> None:
    """Hide reserved primary roles while keeping shared structures selectable."""

    category = WorkflowCategoryCandidate(
        category_id=100,
        category_name="PORTA",
        everyone_can_view=True,
        bot_can_view=True,
    )
    protected = WorkflowTextChannelCandidate(
        channel_id=200,
        channel_name="vestibulum",
        category_id=100,
        everyone_can_view=True,
        everyone_can_send=False,
        bot_can_view=True,
        bot_can_send=True,
        everyone_send_override=False,
    )
    interactive = WorkflowTextChannelCandidate(
        channel_id=201,
        channel_name="salutations",
        category_id=100,
        everyone_can_view=True,
        everyone_can_send=True,
        bot_can_view=True,
        bot_can_send=True,
        everyone_send_override=True,
    )
    discovery = WorkflowStructureDiscoveryResult(
        categories=(category,),
        text_channels=(
            protected,
            interactive,
        ),
        manageable_roles=(
            WorkflowRoleCandidate(
                role_id=300,
                role_name="Membre",
            ),
            WorkflowRoleCandidate(
                role_id=301,
                role_name="interest-test",
            ),
            WorkflowRoleCandidate(
                role_id=302,
                role_name="Libre",
            ),
        ),
        can_create_channels=True,
        can_create_roles=True,
        workflow_candidates=(
            WorkflowStructureCandidate(
                category=category,
                protected_channels=(protected,),
                interactive_channels=(interactive,),
            ),
        ),
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="member",
        command_name="membre",
        command_description="Configure member.",
        title="Membre",
        description=None,
        policy_key="member",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(201,),
        catalogs=(),
        category_id=100,
        management_channel_id=200,
        primary_role_id=300,
    )
    inspection = WorkflowConfigurationInspection(
        guild_id=123,
        workflows=(workflow,),
        ai_role_id=None,
        reserved_role_ids=frozenset(
            {
                300,
            }
        ),
        reserved_role_prefixes=(
            "interest-",
        ),
    )

    service, _, _ = _service(
        discovery,
        inspection,
    )

    guild = MagicMock(
        spec=discord.Guild,
    )
    guild.id = 123

    result = await service.discover_resources(
        guild,
    )

    assert tuple(role.role_id for role in result.manageable_roles) == (
        302,
    )
    assert result.workflow_candidates[0].configured_command_names == (
        "membre",
    )
