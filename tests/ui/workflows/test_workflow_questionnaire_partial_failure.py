from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireSubmission,
)
from claviger.reporting.service import ReportService
from claviger.services.workflows.workflow_questionnaire_coordinator_service import (
    WorkflowQuestionnaireCoordinatorService,
)
from claviger.services.workflows.workflow_role_executor_service import (
    WorkflowRoleExecutionPartialError,
)
from claviger.ui.workflows.workflow_questionnaire_view import _apply


@pytest.mark.asyncio
async def test_partial_role_execution_reports_changes_and_requests_reconciliation() -> None:
    """Expose partial Discord mutation without announcing a false success."""

    coordinator = Mock(
        spec=WorkflowQuestionnaireCoordinatorService,
    )

    partial_error = WorkflowRoleExecutionPartialError(
        added_role_ids=(30,),
        removed_role_ids=(10, 20),
    )
    partial_error.__cause__ = RuntimeError(
        "Discord API failed during role addition."
    )

    coordinator.apply_submission = AsyncMock(
        side_effect=partial_error,
    )

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

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
    interaction.edit_original_response = AsyncMock()

    questionnaire = WorkflowQuestionnaire(
        guild_id=123,
        workflow_key="adult",
        command_name="adult",
        title="Adult",
        description=None,
        primary_role_id=100,
        catalogs=(),
        managed_catalog_role_ids=(),
        ai_enabled=False,
        ai_role_id=None,
        ai_editable=False,
        ai_preference=False,
    )

    submission = WorkflowQuestionnaireSubmission(
        catalogs=(),
    )

    await _apply(
        interaction,
        coordinator=coordinator,
        questionnaire=questionnaire,
        submission=submission,
        report_service=report_service,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "workflow.questionnaire.partial_failure"
    assert event.details is not None
    assert "added_role_ids=(30,)" in event.details
    assert "removed_role_ids=(10, 20)" in event.details
    assert "RuntimeError" in event.details

    interaction.edit_original_response.assert_awaited_once()

    message = interaction.edit_original_response.await_args.kwargs["content"]

    assert "partiellement appliquée" in message
    assert "Relance /adult" in message
    assert "réconcilier" in message
