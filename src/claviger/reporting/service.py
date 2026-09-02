import logging
from collections.abc import Iterable

from claviger.reporting.event import ReportEvent
from claviger.reporting.reporter import Reporter


class ReportService:
    """Dispatch structured events to all configured reporters."""

    def __init__(
        self,
        reporters: Iterable[Reporter],
        logger: logging.Logger | None = None,
    ) -> None:
        self.reporters = tuple(reporters)
        self.logger = logger or logging.getLogger(__name__)

    async def emit(
        self,
        event: ReportEvent,
    ) -> None:
        """Send an event to every reporter without letting one failure stop others."""

        for reporter in self.reporters:
            try:
                await reporter.report(
                    event,
                )
            except Exception:
                self.logger.exception(
                    "Reporter %s failed while handling event %s.",
                    type(reporter).__name__,
                    event.event_type,
                )
