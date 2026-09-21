from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.workflows.generic_workflow_command import (
    create_generic_workflow_command,
)
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfigurationInspectionState,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.reporting.service import ReportService
from claviger.services.workflows.workflow_questionnaire_coordinator_service import (
    WorkflowQuestionnaireAIUnavailableError,
    WorkflowQuestionnaireCoordinatorService,
)


@pytest.mark.asyncio
async def test_generic_workflow_reports_missing_configured_ai_role_actionably() -> None:
    """Tell ADMIN when a configured AI role disappeared from live Discord."""

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="adult",
        command_name="adult",
        command_description="Configure tes accès.",
        title="Adult",
        description=None,
        policy_key="adult",
        channel_mode="open",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(),
        primary_role_id=300,
    )

    coordinator = Mock(
        spec=WorkflowQuestionnaireCoordinatorService,
    )
    coordinator.build_questionnaire = AsyncMock(
        side_effect=WorkflowQuestionnaireAIUnavailableError(
            state=GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND,
            ai_role_id=900,
        )
    )

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

    command = create_generic_workflow_command(
        workflow=workflow,
        coordinator=coordinator,
        report_service=report_service,
    )

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123
    guild.name = "Laboratorium"

    member = Mock(
        spec=discord.Member,
    )
    member.id = 42
    member.display_name = "Yrekk"

    interaction.guild = guild
    interaction.user = member
    interaction.channel_id = 200
    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    await command.callback(
        interaction,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "workflow.ai_configuration_drift"
    assert event.title == "Rôle IA configuré introuvable"
    assert event.details is not None
    assert "state=enabled_role_not_found" in event.details
    assert "ai_role_id=900" in event.details
    assert "Recréer ou réaffecter le rôle IA" in event.details

    interaction.response.send_message.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "administrateur a été prévenu" in message
