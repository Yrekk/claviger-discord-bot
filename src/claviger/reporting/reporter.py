from typing import Protocol

from claviger.reporting.event import ReportEvent


class ReporterUnavailableError(RuntimeError):
    """Raised when a reporter has no usable destination for an event yet."""


class Reporter(Protocol):
    """Define a destination capable of receiving structured reports."""

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Send or persist a report event."""
        ...
