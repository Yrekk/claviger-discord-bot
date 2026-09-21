import logging
from unittest.mock import AsyncMock, Mock

import pytest

from claviger.reporting.discord_bootstrap_dm import DiscordBootstrapDMReporter
from claviger.reporting.discord_forum import DiscordForumReporter
from claviger.reporting.discord_human import DiscordHumanReporter
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.reporter import ReporterUnavailableError


def _event(
    *,
    severity: ReportSeverity = ReportSeverity.ERROR,
) -> ReportEvent:
    return ReportEvent(
        event_type="test.incident",
        severity=severity,
        title="Incident",
        summary="Something failed.",
        guild_id=123,
        actor_id=42,
    )


def _reporter() -> tuple[DiscordHumanReporter, Mock, Mock, Mock]:
    forum_reporter = Mock(spec=DiscordForumReporter)
    forum_reporter.report = AsyncMock()

    fallback_dm_reporter = Mock(spec=DiscordBootstrapDMReporter)
    fallback_dm_reporter.report = AsyncMock()

    logger = Mock(spec=logging.Logger)

    reporter = DiscordHumanReporter(
        forum_reporter=forum_reporter,
        fallback_dm_reporter=fallback_dm_reporter,
        logger=logger,
    )

    return reporter, forum_reporter, fallback_dm_reporter, logger


@pytest.mark.asyncio
async def test_human_reporter_uses_forum_without_dm_when_admin_routing_works() -> None:
    reporter, forum_reporter, fallback_dm_reporter, logger = _reporter()
    event = _event()

    await reporter.report(event)

    forum_reporter.report.assert_awaited_once_with(event)
    fallback_dm_reporter.report.assert_not_awaited()
    logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_human_reporter_forces_dm_when_incident_forum_fails() -> None:
    reporter, forum_reporter, fallback_dm_reporter, logger = _reporter()
    forum_reporter.report.side_effect = RuntimeError("Forum deleted.")
    event = _event()

    await reporter.report(event)

    fallback_dm_reporter.report.assert_awaited_once_with(
        event,
        force=True,
    )
    logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_human_reporter_does_not_dm_normal_activity_when_forum_fails() -> None:
    reporter, forum_reporter, fallback_dm_reporter, _ = _reporter()
    forum_reporter.report.side_effect = RuntimeError("Activity forum unavailable.")

    with pytest.raises(
        RuntimeError,
        match="Activity forum unavailable",
    ):
        await reporter.report(
            _event(
                severity=ReportSeverity.INFO,
            )
        )

    fallback_dm_reporter.report.assert_not_awaited()


@pytest.mark.asyncio
async def test_human_reporter_reports_unavailable_when_forum_and_dm_fail() -> None:
    reporter, forum_reporter, fallback_dm_reporter, _ = _reporter()
    forum_reporter.report.side_effect = RuntimeError("Forum unavailable.")
    fallback_dm_reporter.report.side_effect = RuntimeError("DM closed.")

    with pytest.raises(
        ReporterUnavailableError,
        match="fallback",
    ):
        await reporter.report(
            _event(),
        )
