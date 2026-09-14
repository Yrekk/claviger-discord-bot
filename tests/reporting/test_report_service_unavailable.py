import logging
from unittest.mock import AsyncMock, Mock

import pytest

from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.reporter import ReporterUnavailableError
from claviger.reporting.service import ReportService


@pytest.mark.asyncio
async def test_report_service_logs_unconfigured_destination_without_traceback() -> None:
    """Treat bootstrap routing absence as unavailable, not as a reporter crash."""

    reporter = Mock()
    reporter.report = AsyncMock(
        side_effect=ReporterUnavailableError(
            "Guild has no ADMIN configuration yet."
        )
    )

    logger = Mock(
        spec=logging.Logger,
    )

    service = ReportService(
        reporters=(reporter,),
        logger=logger,
    )

    event = ReportEvent(
        event_type="database.migrate.success",
        severity=ReportSeverity.INFO,
        title="Database migrated",
        summary="Migration completed.",
        guild_id=123,
    )

    await service.emit(
        event,
    )

    logger.warning.assert_called_once_with(
        "Reporter %s unavailable while handling event %s: %s",
        type(reporter).__name__,
        event.event_type,
        reporter.report.side_effect,
    )
    logger.exception.assert_not_called()
