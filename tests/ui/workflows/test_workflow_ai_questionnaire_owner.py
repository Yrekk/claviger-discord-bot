from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.reporting.service import ReportService
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)
from claviger.ui.workflows.workflow_ai_questionnaire_owner_view import (
    WorkflowAIQuestionnaireOwnerSelectionView,
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


def _interaction() -> Mock:
    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123
    guild.name = "Laboratorium"

    user = Mock(
        spec=discord.Member,
    )
    user.id = 42
    user.display_name = "Yrekk"

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()

    return interaction


@pytest.mark.asyncio
async def test_owner_selection_moves_single_pointer_and_reports_activity() -> None:
    """Switch ownership through the service without editing a second workflow row."""

    owner_service = Mock(
        spec=GuildAIQuestionnaireOwnerService,
    )
    owner_service.assign = AsyncMock(
        return_value=(
            "gaming",
            "member",
        )
    )

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

    workflows = (
        _workflow("gaming"),
        _workflow("member"),
    )

    view = WorkflowAIQuestionnaireOwnerSelectionView(
        owner_service=owner_service,
        report_service=report_service,
        workflows=workflows,
        actor_id=42,
        guild_id=123,
        current_owner_key="gaming",
    )

    select = view.children[0]
    select._values = [
        "member",
    ]

    interaction = _interaction()

    await select.callback(
        interaction,
    )

    owner_service.assign.assert_awaited_once_with(
        guild_id=123,
        workflow_key="member",
    )
    report_service.emit.assert_awaited_once()

    message = interaction.edit_original_response.await_args.kwargs["content"]

    assert "/member" in message
    assert "unique workflow" in message
