from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock

import discord
import pytest

from claviger.models.runtime.guild_ai_questionnaire_owner_model import (
    GuildAIQuestionnaireOwnerInspection,
)
from claviger.models.workflows.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
from claviger.models.workflows.workflow_configuration_model import (
    WorkflowResourceSelection,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.models.workflows.workflow_structure_provisioning_model import (
    WorkflowStructureProvisioningResult,
)
from claviger.reporting.service import ReportService
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.ui.workflows.workflow_configuration_session import (
    WorkflowConfigurationSession,
)
from claviger.ui.workflows.workflow_configuration_view import (
    WorkflowAIQuestionnaireChoiceView,
    WorkflowConfigurationReviewView,
    _advance_after_resource,
)


def _session(
    *,
    owner_service: Mock,
    report_service: Mock | None = None,
) -> WorkflowConfigurationSession:
    """Create one complete workflow UI session for IA ownership tests."""

    session = WorkflowConfigurationSession(
        guild_id=123,
        actor_id=42,
        discovery=WorkflowStructureDiscoveryResult(
            categories=(),
            text_channels=(),
            manageable_roles=(),
            can_create_channels=True,
            can_create_roles=True,
        ),
        report_service=report_service,
        ai_questionnaire_owner_service=owner_service,
    )
    session.title = "Gaming"
    session.command_name = "gamer"
    session.questionnaire_role_prefix = "gaming-"
    session.category = WorkflowResourceSelection(
        mode="existing",
        resource_id=100,
    )
    session.management_channel = WorkflowResourceSelection(
        mode="existing",
        resource_id=200,
    )
    session.execution_channel = WorkflowResourceSelection(
        mode="existing",
        resource_id=201,
    )
    session.primary_role = WorkflowResourceSelection(
        mode="existing",
        resource_id=300,
    )
    return session


def _interaction() -> SimpleNamespace:
    """Create one deterministic guild interaction stub."""

    return SimpleNamespace(
        guild=SimpleNamespace(
            id=123,
            name="Laboratorium",
        ),
        user=SimpleNamespace(
            id=42,
            display_name="Yrekk",
        ),
        response=SimpleNamespace(
            edit_message=AsyncMock(),
            defer=AsyncMock(),
            send_message=AsyncMock(),
        ),
        edit_original_response=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_primary_role_step_offers_ai_owner_choice_without_persisted_workflow() -> None:
    """Offer IA ownership even when discovery recovered an unpersisted workflow."""

    owner_service = Mock(spec=GuildAIQuestionnaireOwnerService)
    owner_service.inspect = AsyncMock(
        return_value=GuildAIQuestionnaireOwnerInspection(
            guild_id=123,
            owner_workflow_key=None,
            workflows=(),
            ai_enabled=True,
            ai_role_id=900,
        )
    )
    session = _session(owner_service=owner_service)
    interaction = _interaction()
    coordinator = MagicMock(spec=WorkflowConfigurationCoordinatorService)

    await _advance_after_resource(
        interaction,
        coordinator=coordinator,
        session=session,
        resource="primary_role",
        admin_command_name="experimentum",
    )

    owner_service.inspect.assert_awaited_once_with(123)
    call = interaction.response.edit_message.await_args
    assert "Option IA de ce workflow" in call.kwargs["content"]
    assert isinstance(call.kwargs["view"], WorkflowAIQuestionnaireChoiceView)


@pytest.mark.asyncio
async def test_accepting_ai_owner_choice_stages_without_mutation() -> None:
    """Keep the IA choice local until the final workflow confirmation."""

    owner_service = Mock(spec=GuildAIQuestionnaireOwnerService)
    owner_service.assign = AsyncMock()
    session = _session(owner_service=owner_service)
    interaction = _interaction()
    coordinator = MagicMock(spec=WorkflowConfigurationCoordinatorService)
    view = WorkflowAIQuestionnaireChoiceView(
        coordinator=coordinator,
        session=session,
        admin_command_name="experimentum",
    )
    yes_button = next(
        child
        for child in view.children
        if isinstance(child, discord.ui.Button)
        and child.label == "Oui, sur ce workflow"
    )

    await yes_button.callback(interaction)

    assert session.ai_questionnaire_owner is True
    owner_service.assign.assert_not_awaited()
    call = interaction.response.edit_message.await_args
    assert "Résumé du workflow" in call.kwargs["content"]
    assert "unique propriétaire" in call.kwargs["content"]


@pytest.mark.asyncio
async def test_final_confirmation_assigns_ai_owner_after_workflow_persistence() -> None:
    """Persist the workflow before assigning its unique IA ownership."""

    owner_service = Mock(spec=GuildAIQuestionnaireOwnerService)
    owner_service.assign = AsyncMock(return_value=(None, "gamer"))
    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()
    session = _session(
        owner_service=owner_service,
        report_service=report_service,
    )
    session.ai_questionnaire_owner = True

    coordinator = MagicMock(spec=WorkflowConfigurationCoordinatorService)
    coordinator.configure = AsyncMock(
        return_value=WorkflowStructureProvisioningResult(
            guild_id=123,
            configuration=ResolvedWorkflowConfiguration(
                guild_id=123,
                workflow_key="gamer",
                title="Gaming",
                description=None,
                command_name="gamer",
                command_description="Configure Gaming.",
                category_id=100,
                management_channel_id=200,
                execution_channel_id=201,
                primary_role_id=300,
                questionnaire_role_prefix="gaming-",
            ),
        )
    )
    interaction = _interaction()
    view = WorkflowConfigurationReviewView(
        coordinator=coordinator,
        session=session,
        admin_command_name="experimentum",
    )
    confirm_button = next(
        child
        for child in view.children
        if isinstance(child, discord.ui.Button)
        and child.label == "Créer / enregistrer le workflow"
    )

    await confirm_button.callback(interaction)

    coordinator.configure.assert_awaited_once()
    owner_service.assign.assert_awaited_once_with(
        guild_id=123,
        workflow_key="gamer",
    )
    final_content = interaction.edit_original_response.await_args.kwargs["content"]
    assert "Question IA" in final_content
    assert "/gamer" in final_content
    assert any(
        call.args[0].event_type == "workflow.ai_questionnaire.owner_changed"
        for call in report_service.emit.await_args_list
    )
