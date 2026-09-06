from dataclasses import FrozenInstanceError
from datetime import timezone

import pytest

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)


def test_report_event_stores_required_information() -> None:
    """Store the core information required by all reporters."""
    event = ReportEvent(
        event_type="database.initialize.failed",
        severity=ReportSeverity.ERROR,
        title="Database initialization failed",
        summary="SQLite could not be initialized.",
    )

    assert event.event_type == "database.initialize.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.title == "Database initialization failed"
    assert event.summary == "SQLite could not be initialized."


def test_report_event_supports_optional_context() -> None:
    """Store optional guild, actor, target and technical details."""
    event = ReportEvent(
        event_type="role.assign.success",
        severity=ReportSeverity.INFO,
        title="Role assigned",
        summary="A Discord role was assigned.",
        details="Role: Membre",
        guild_id=123,
        actor_id=456,
        target_id=789,
    )

    assert event.details == "Role: Membre"
    assert event.guild_id == 123
    assert event.actor_id == 456
    assert event.target_id == 789


def test_report_event_uses_timezone_aware_utc_timestamp() -> None:
    """Timestamp reports automatically using timezone-aware UTC."""
    event = ReportEvent(
        event_type="test.event",
        severity=ReportSeverity.INFO,
        title="Test",
        summary="Test event.",
    )

    assert event.occurred_at.tzinfo == timezone.utc


def test_report_event_is_immutable() -> None:
    """Prevent reporters from accidentally modifying an emitted event."""
    event = ReportEvent(
        event_type="test.event",
        severity=ReportSeverity.INFO,
        title="Test",
        summary="Test event.",
    )

    with pytest.raises(FrozenInstanceError):
        setattr(
            event,
            "title",
            "Modified",
        )
