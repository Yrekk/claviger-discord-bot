from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.models.runtime.guild_ai_configuration_model import GuildAIConfiguration
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.runtime.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.runtime.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.runtime.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)

pytestmark = pytest.mark.asyncio


async def test_configuration_inspection_includes_workflow_and_ai_diagnostics() -> None:
    """Hydrate detailed diagnostics only after database ownership is validated."""

    guild = Mock(spec=discord.Guild)
    guild.id = 123

    database_status_service = Mock(spec=DatabaseStatusService)
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=12,
            target_version=12,
        )
    )

    ownership_service = Mock(spec=DatabaseOwnershipService)
    ownership_service.get_owner_application_id = AsyncMock(
        return_value=789,
    )

    admin_service = Mock(spec=AdminConfigurationCoordinatorService)
    admin_service.inspect = AsyncMock(
        return_value=Mock(),
    )

    policy_resolver = Mock(spec=PolicyResolver)
    policy_resolver.inspect = AsyncMock(
        return_value=Mock(),
    )

    metrics_repository = Mock(spec=GuildConfigurationMetricsRepository)
    metrics_repository.get = AsyncMock(
        return_value=Mock(),
    )

    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_marker = Mock()
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            workflow_marker,
        )
    )

    workflow_discovery = Mock(spec=WorkflowStructureDiscoveryService)
    discovery_marker = Mock()
    workflow_discovery.discover = AsyncMock(
        return_value=discovery_marker,
    )

    ai_repository = Mock(spec=GuildAIConfigurationRepository)
    ai_configuration = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=True,
        ai_role_id=900,
    )
    ai_repository.get = AsyncMock(
        return_value=ai_configuration,
    )

    owner_repository = Mock(spec=GuildAIQuestionnaireOwnerRepository)
    owner_repository.get = AsyncMock(
        return_value="gamer",
    )

    service = GuildConfigurationInspectionService(
        database_status_service=database_status_service,
        database_ownership_service=ownership_service,
        admin_configuration_coordinator_service=admin_service,
        policy_resolver=policy_resolver,
        metrics_repository=metrics_repository,
        workflow_repository=workflow_repository,
        workflow_discovery_service=workflow_discovery,
        ai_repository=ai_repository,
        ai_owner_repository=owner_repository,
    )

    result = await service.inspect(
        guild,
        application_id=789,
    )

    assert result.workflows == (
        workflow_marker,
    )
    assert result.workflow_discovery is discovery_marker
    assert result.ai_configuration == ai_configuration
    assert result.ai_questionnaire_owner_workflow_key == "gamer"

    workflow_repository.list_for_guild.assert_awaited_once_with(
        123,
    )
    workflow_discovery.discover.assert_awaited_once_with(
        guild,
    )
    ai_repository.get.assert_awaited_once_with(
        123,
    )
    owner_repository.get.assert_awaited_once_with(
        123,
    )
