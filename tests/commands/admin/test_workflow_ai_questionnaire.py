from unittest.mock import AsyncMock, Mock

import pytest

from claviger.models.runtime.guild_ai_questionnaire_owner_model import (
    GuildAIQuestionnaireOwnerInspection,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)
from claviger.ui.workflows.workflow_ai_questionnaire_owner_view import (
    WorkflowAIQuestionnaireOwnerCurrentView,
    WorkflowAIQuestionnaireOwnerSelectionView,
)

from .helpers import (
    create_interaction,
    create_test_group,
)


def _workflow(
    key: str,
) -> WorkflowDefinition:
    return WorkflowDefinition(
        guild_id=123,
        workflow_key=key,
        command_name=key,
        command_description=f"Configure {key}.",
        title=key.title(),
        description=None,
        policy_key=key,
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(),
    )


def _command(
    inspection: GuildAIQuestionnaireOwnerInspection,
):
    role_service = Mock(
        spec=RoleDiscoveryService,
    )
    owner_service = Mock(
        spec=GuildAIQuestionnaireOwnerService,
    )
    owner_service.inspect = AsyncMock(
        return_value=inspection,
    )
    owner_service.assign = AsyncMock()

    group, _, _, _, report_service = create_test_group(
        role_service,
        ai_questionnaire_owner_service=owner_service,
    )

    workflow_group = group.get_command(
        "workflow",
    )
    assert workflow_group is not None

    command = workflow_group.get_command(
        "ai-questionnaire",
    )
    assert command is not None

    return (
        command,
        owner_service,
        report_service,
    )


@pytest.mark.asyncio
async def test_ai_questionnaire_command_offers_first_owner_selection() -> None:
    """Discover active workflows when no owner has been assigned yet."""

    workflows = (
        _workflow("gaming"),
        _workflow("member"),
    )
    inspection = GuildAIQuestionnaireOwnerInspection(
        guild_id=123,
        owner_workflow_key=None,
        workflows=workflows,
        ai_enabled=True,
        ai_role_id=900,
    )
    command, owner_service, _ = _command(
        inspection,
    )
    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    owner_service.inspect.assert_awaited_once_with(
        123,
    )

    kwargs = interaction.followup.send.await_args.kwargs

    assert isinstance(
        kwargs["view"],
        WorkflowAIQuestionnaireOwnerSelectionView,
    )
    assert "unique propriétaire" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_ai_questionnaire_command_requires_confirmation_before_switch() -> None:
    """Show the current owner before presenting alternate workflows."""

    workflows = (
        _workflow("gaming"),
        _workflow("member"),
    )
    inspection = GuildAIQuestionnaireOwnerInspection(
        guild_id=123,
        owner_workflow_key="gaming",
        workflows=workflows,
        ai_enabled=True,
        ai_role_id=900,
    )
    command, _, _ = _command(
        inspection,
    )
    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    kwargs = interaction.followup.send.await_args.kwargs

    assert isinstance(
        kwargs["view"],
        WorkflowAIQuestionnaireOwnerCurrentView,
    )
    assert "/gaming" in interaction.followup.send.await_args.args[0]
    assert "déplacer" in interaction.followup.send.await_args.args[0]
