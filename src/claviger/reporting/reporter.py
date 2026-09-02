from typing import Protocol

from claviger.reporting.event import ReportEvent


class Reporter(Protocol):
    """Define a destination capable of receiving structured reports."""

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Send or persist a report event."""
        ...
