from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
)
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireSubmission,
)
from claviger.models.workflows.workflow_role_execution_result_model import (
    WorkflowRoleExecutionResult,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.catalog_entry_synchronization_service import (
    CatalogEntrySynchronizationService,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationService,
)
from claviger.services.workflows.workflow_questionnaire_coordinator_service import (
    WorkflowQuestionnaireAIUnavailableError,
    WorkflowQuestionnaireCoordinatorService,
)
from claviger.services.workflows.workflow_questionnaire_planner_service import (
    WorkflowQuestionnairePlannerService,
)
from claviger.services.workflows.workflow_role_executor_service import (
    WorkflowRoleExecutorService,
)
from claviger.services.workflows.workflow_role_planner_service import (
    WorkflowRolePlannerService,
)

pytestmark = pytest.mark.asyncio


def _workflow() -> WorkflowDefinition:
    catalog = CatalogDefinition(
        guild_id=123,
        catalog_key="access",
        role_prefix="access-",
        display_name="Accès",
        entry_name="Accès",
        description=None,
        sort_order=0,
        enabled=True,
    )
    return WorkflowDefinition(
        guild_id=123,
        workflow_key="noctis",
        command_name="noctis",
        command_description="Configure tes accès.",
        title="Noctis",
        description=None,
        policy_key="noctis",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(200,),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=catalog,
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        primary_role_id=300,
    )


async def test_coordinator_rebuilds_questionnaire_before_submission_execution() -> None:
    """Rebuild fresh persistence and member state before execution."""

    workflow_repository = MagicMock(spec=WorkflowDefinitionRepository)
    workflow_repository.get = AsyncMock(return_value=_workflow())

    catalog_repository = MagicMock(spec=CatalogEntryRepository)
    catalog_sync_service = MagicMock(spec=CatalogEntrySynchronizationService)
    catalog_sync_service.synchronize = AsyncMock(return_value=())

    ai_configuration_service = MagicMock(spec=GuildAIConfigurationService)
    ai_configuration_service.inspect = AsyncMock(
        return_value=GuildAIConfigurationInspection(
            guild_id=123,
            state=GuildAIConfigurationInspectionState.READY,
            configuration=GuildAIConfiguration(
                guild_id=123,
                ai_enabled=True,
                ai_role_id=900,
            ),
            role_name="option-ia",
        )
    )

    owner_repository = MagicMock(spec=GuildAIQuestionnaireOwnerRepository)
    owner_repository.get = AsyncMock(return_value="noctis")

    questionnaire = WorkflowQuestionnaire(
        guild_id=123,
        workflow_key="noctis",
        command_name="noctis",
        title="Noctis",
        description=None,
        primary_role_id=300,
        catalogs=(),
        managed_catalog_role_ids=(),
        ai_enabled=True,
        ai_role_id=900,
        ai_editable=True,
        ai_preference=True,
    )

    questionnaire_planner = MagicMock(spec=WorkflowQuestionnairePlannerService)
    questionnaire_planner.build.return_value = questionnaire

    role_planner = MagicMock(spec=WorkflowRolePlannerService)
    role_planner.build_plan.return_value = SimpleNamespace(
        has_changes=False,
        add_role_ids=(),
        remove_role_ids=(),
    )

    role_executor = MagicMock(spec=WorkflowRoleExecutorService)
    role_executor.execute = AsyncMock(
        return_value=WorkflowRoleExecutionResult(),
    )

    coordinator = WorkflowQuestionnaireCoordinatorService(
        workflow_repository=workflow_repository,
        catalog_entry_repository=catalog_repository,
        catalog_sync_service=catalog_sync_service,
        ai_configuration_service=ai_configuration_service,
        owner_repository=owner_repository,
        questionnaire_planner=questionnaire_planner,
        role_planner=role_planner,
        role_executor=role_executor,
    )

    guild = MagicMock(spec=discord.Guild)
    guild.id = 123
    member = MagicMock(spec=discord.Member)
    member.roles = [
        SimpleNamespace(
            id=900,
        )
    ]

    submission = WorkflowQuestionnaireSubmission(
        catalogs=(),
        ai_preference=True,
    )

    result = await coordinator.apply_submission(
        guild=guild,
        member=member,
        workflow_key="noctis",
        submission=submission,
    )

    assert result == WorkflowRoleExecutionResult()
    workflow_repository.get.assert_awaited_once_with(
        guild_id=123,
        workflow_key="noctis",
    )
    catalog_sync_service.synchronize.assert_awaited_once()
    role_planner.build_plan.assert_called_once()
    role_executor.execute.assert_awaited_once()


async def test_coordinator_rejects_missing_live_ai_role_for_consumer_workflow() -> None:
    """Do not reinterpret a deleted configured AI role as preference disabled."""

    workflow_repository = MagicMock(spec=WorkflowDefinitionRepository)
    workflow_repository.get = AsyncMock(return_value=_workflow())

    catalog_repository = MagicMock(spec=CatalogEntryRepository)
    catalog_sync_service = MagicMock(spec=CatalogEntrySynchronizationService)
    catalog_sync_service.synchronize = AsyncMock(return_value=())

    ai_configuration_service = MagicMock(spec=GuildAIConfigurationService)
    ai_configuration_service.inspect = AsyncMock(
        return_value=GuildAIConfigurationInspection(
            guild_id=123,
            state=GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND,
            configuration=GuildAIConfiguration(
                guild_id=123,
                ai_enabled=True,
                ai_role_id=900,
            ),
        )
    )

    owner_repository = MagicMock(spec=GuildAIQuestionnaireOwnerRepository)
    owner_repository.get = AsyncMock(return_value="membre")

    questionnaire_planner = MagicMock(spec=WorkflowQuestionnairePlannerService)
    role_planner = MagicMock(spec=WorkflowRolePlannerService)
    role_executor = MagicMock(spec=WorkflowRoleExecutorService)

    coordinator = WorkflowQuestionnaireCoordinatorService(
        workflow_repository=workflow_repository,
        catalog_entry_repository=catalog_repository,
        catalog_sync_service=catalog_sync_service,
        ai_configuration_service=ai_configuration_service,
        owner_repository=owner_repository,
        questionnaire_planner=questionnaire_planner,
        role_planner=role_planner,
        role_executor=role_executor,
    )

    guild = MagicMock(spec=discord.Guild)
    guild.id = 123
    member = MagicMock(spec=discord.Member)
    member.roles = []

    with pytest.raises(
        WorkflowQuestionnaireAIUnavailableError,
        match="enabled_role_not_found",
    ):
        await coordinator.build_questionnaire(
            guild=guild,
            member=member,
            workflow_key="noctis",
        )

    questionnaire_planner.build.assert_not_called()
