from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.reporting.service import ReportService
from claviger.ui.workflows.workflow_configuration_session import (
    WorkflowConfigurationSession,
)
from claviger.ui.workflows.workflow_configuration_view import (
    _emit_workflow_configuration_failed,
    _normalize_command_name,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("gamer", "gamer"),
        (" /gamer ", "gamer"),
        ("//gamer", "/gamer"),
    ],
)
def test_normalize_command_name_removes_only_one_leading_slash(
    raw: str,
    expected: str,
) -> None:
    """Accept the natural Discord slash without weakening backend validation."""

    assert _normalize_command_name(
        raw,
    ) == expected


@pytest.mark.asyncio
async def test_backend_workflow_failure_emits_admin_report() -> None:
    """Route genuine backend incidents through ReportService."""

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

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
    )

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

    error = RuntimeError(
        "Provisioning exploded.",
    )

    await _emit_workflow_configuration_failed(
        interaction,
        session=session,
        error=error,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "workflow.configuration.failed"
    assert event.guild_id == 123
    assert event.actor_id == 42
    assert event.details is not None
    assert "RuntimeError" in event.details
