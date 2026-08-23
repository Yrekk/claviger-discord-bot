from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum


class ReportSeverity(StrEnum):
    """Define the severity of a Claviger report."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ReportEvent:
    """Describe a structured event that can be sent to multiple reporters."""

    event_type: str
    severity: ReportSeverity
    title: str
    summary: str

    details: str | None = None

    guild_id: int | None = None
    guild_label: str | None = None

    actor_id: int | None = None
    actor_label: str | None = None

    target_id: int | None = None
    target_label: str | None = None

    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc,
        )
    )