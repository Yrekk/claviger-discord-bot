import logging
from unittest.mock import Mock

import pytest

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.python_logger import (
    PythonLoggingReporter,
)


@pytest.mark.asyncio
async def test_python_logging_reporter_logs_event() -> None:
    """Write report events through the configured Python logger."""
    logger = Mock(
        spec=logging.Logger,
    )

    reporter = PythonLoggingReporter(
        logger=logger,
    )

    event = ReportEvent(
        event_type="database.initialize.success",
        severity=ReportSeverity.INFO,
        title="Database initialized",
        summary="SQLite initialization completed.",
    )

    await reporter.report(
        event,
    )

    logger.log.assert_called_once_with(
        logging.INFO,
        (
            "[database.initialize.success] "
            "Database initialized — "
            "SQLite initialization completed."
        ),
    )


@pytest.mark.asyncio
async def test_python_logging_reporter_maps_error_severity() -> None:
    """Map report severity to the appropriate Python logging level."""
    logger = Mock(
        spec=logging.Logger,
    )

    reporter = PythonLoggingReporter(
        logger=logger,
    )

    event = ReportEvent(
        event_type="database.initialize.failed",
        severity=ReportSeverity.ERROR,
        title="Database initialization failed",
        summary="SQLite could not be initialized.",
    )

    await reporter.report(
        event,
    )

    assert logger.log.call_args.args[0] == logging.ERROR


@pytest.mark.asyncio
async def test_python_logging_reporter_includes_details_and_context() -> None:
    """Include technical and Discord context in the log message."""
    logger = Mock(
        spec=logging.Logger,
    )

    reporter = PythonLoggingReporter(
        logger=logger,
    )

    event = ReportEvent(
        event_type="role.assign.failed",
        severity=ReportSeverity.ERROR,
        title="Role assignment failed",
        summary="Claviger could not assign the role.",
        details="Discord returned Forbidden.",
        guild_id=123,
        actor_id=456,
        target_id=789,
    )

    await reporter.report(
        event,
    )

    message = logger.log.call_args.args[1]

    assert "Discord returned Forbidden." in message
    assert "guild_id=123" in message
    assert "actor_id=456" in message
    assert "target_id=789" in message