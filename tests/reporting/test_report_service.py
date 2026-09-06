import logging
from unittest.mock import AsyncMock, Mock

import pytest

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.service import ReportService


def create_event() -> ReportEvent:
    """Create a report event used by dispatch tests."""
    return ReportEvent(
        event_type="test.event",
        severity=ReportSeverity.INFO,
        title="Test event",
        summary="A test event occurred.",
    )


def create_reporter() -> Mock:
    """Create an asynchronous mocked reporter."""
    reporter = Mock()
    reporter.report = AsyncMock()

    return reporter


@pytest.mark.asyncio
async def test_report_service_dispatches_event_to_all_reporters() -> None:
    """Send an event to every configured reporter."""
    first = create_reporter()
    second = create_reporter()

    service = ReportService(
        reporters=[
            first,
            second,
        ],
    )

    event = create_event()

    await service.emit(
        event,
    )

    first.report.assert_awaited_once_with(
        event,
    )
    second.report.assert_awaited_once_with(
        event,
    )


@pytest.mark.asyncio
async def test_report_service_continues_when_reporter_fails() -> None:
    """Continue dispatching when one reporter raises an exception."""
    failing = create_reporter()
    failing.report.side_effect = RuntimeError("Discord unavailable.")

    working = create_reporter()

    service = ReportService(
        reporters=[
            failing,
            working,
        ],
    )

    event = create_event()

    await service.emit(
        event,
    )

    failing.report.assert_awaited_once_with(
        event,
    )
    working.report.assert_awaited_once_with(
        event,
    )


@pytest.mark.asyncio
async def test_report_service_logs_reporter_failure() -> None:
    """Log reporter failures without propagating them."""
    reporter = create_reporter()
    reporter.report.side_effect = RuntimeError("Reporter exploded.")

    logger = Mock(
        spec=logging.Logger,
    )

    service = ReportService(
        reporters=[
            reporter,
        ],
        logger=logger,
    )

    event = create_event()

    await service.emit(
        event,
    )

    logger.exception.assert_called_once_with(
        "Reporter %s failed while handling event %s.",
        type(reporter).__name__,
        event.event_type,
    )
