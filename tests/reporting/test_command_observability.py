from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from claviger.reporting.command_observability import CommandObservabilityService
from claviger.reporting.event import ReportSeverity
from claviger.reporting.python_logger import PythonLoggingReporter
from claviger.reporting.service import ReportService
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

pytestmark = pytest.mark.asyncio


def _interaction(
    *,
    data: dict | None = None,
    channel_id: int = 200,
) -> Mock:
    """Create one deterministic application-command interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123
    guild.name = "Laboratium"

    user = Mock(
        spec=discord.Member,
    )
    user.id = 456
    user.display_name = "Tester"

    channel = Mock(
        spec=discord.TextChannel,
    )
    channel.name = "admin-commands"

    interaction.guild = guild
    interaction.user = user
    interaction.channel = channel
    interaction.channel_id = channel_id
    interaction.data = data or {
        "name": "experimentum",
        "type": 1,
        "options": [
            {
                "name": "roles",
                "type": 2,
                "options": [
                    {
                        "name": "scan",
                        "type": 1,
                        "options": [],
                    }
                ],
            }
        ],
    }

    return interaction


def _service(
    *,
    configured: bool,
) -> tuple[
    CommandObservabilityService,
    Mock,
    Mock,
    Mock,
]:
    """Create observability dependencies with deterministic routing state."""

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

    repository = Mock(
        spec=GuildAdminConfigurationRepository,
    )
    repository.get = AsyncMock(
        return_value=(object() if configured else None),
    )

    local_reporter = Mock(
        spec=PythonLoggingReporter,
    )
    local_reporter.report = AsyncMock()

    service = CommandObservabilityService(
        report_service=report_service,
        admin_configuration_repository=repository,
        local_reporter=local_reporter,
    )

    return service, report_service, repository, local_reporter


async def test_configured_guild_routes_completion_through_report_service() -> None:
    """Send completed command activity to console and report-activity."""

    service, report_service, repository, local_reporter = _service(
        configured=True,
    )

    await service.record_completion(
        _interaction(),
    )

    repository.get.assert_awaited_once_with(
        123,
    )

    local_reporter.report.assert_not_awaited()
    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "command.completed"
    assert event.severity == ReportSeverity.INFO
    assert "/experimentum roles scan" in event.summary
    assert "#admin-commands" in event.details


async def test_unconfigured_guild_keeps_completion_in_console_only() -> None:
    """Avoid reporter-unavailable noise before report-activity can exist."""

    service, report_service, repository, local_reporter = _service(
        configured=False,
    )

    await service.record_completion(
        _interaction(),
    )

    repository.get.assert_awaited_once_with(
        123,
    )

    report_service.emit.assert_not_awaited()
    local_reporter.report.assert_awaited_once()

    event = local_reporter.report.await_args.args[0]

    assert event.event_type == "command.completed"
    assert event.severity == ReportSeverity.INFO


async def test_command_arguments_are_never_written_to_completion_event() -> None:
    """Keep arbitrary user-provided option values out of operational logs."""

    service, report_service, _, _ = _service(
        configured=True,
    )

    interaction = _interaction(
        data={
            "name": "experimentum",
            "type": 1,
            "options": [
                {
                    "name": "say",
                    "type": 1,
                    "options": [
                        {
                            "name": "message",
                            "type": 3,
                            "value": "TOP-SECRET-PAYLOAD",
                        }
                    ],
                }
            ],
        }
    )

    await service.record_completion(
        interaction,
    )

    event = report_service.emit.await_args.args[0]

    assert "/experimentum say" in event.summary
    assert "TOP-SECRET-PAYLOAD" not in event.summary
    assert "TOP-SECRET-PAYLOAD" not in event.details


async def test_expected_rejection_is_info_activity() -> None:
    """Treat an explained check rejection as normal operational activity."""

    service, report_service, _, _ = _service(
        configured=True,
    )

    await service.record_rejection(
        _interaction(),
        app_commands.CheckFailure("routing rejected"),
    )

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "command.rejected"
    assert event.severity == ReportSeverity.INFO
    assert "refus attendu" in event.details


async def test_unhandled_callback_error_is_error_with_traceback() -> None:
    """Preserve the original callback exception and traceback for diagnostics."""

    service, report_service, _, _ = _service(
        configured=True,
    )

    async def failing_command(
        interaction: discord.Interaction,
    ) -> None:
        raise ValueError("boom")

    command = app_commands.Command(
        name="boom",
        description="Boom.",
        callback=failing_command,
    )

    try:
        raise ValueError("boom")
    except ValueError as original_error:
        error = app_commands.CommandInvokeError(
            command,
            original_error,
        )

    await service.record_failure(
        _interaction(),
        error,
    )

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "command.failed"
    assert event.severity == ReportSeverity.ERROR
    assert "ValueError: boom" in event.details
    assert "Traceback:" in event.details
