import logging

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)


SEVERITY_LEVELS = {
    ReportSeverity.INFO: logging.INFO,
    ReportSeverity.WARNING: logging.WARNING,
    ReportSeverity.ERROR: logging.ERROR,
    ReportSeverity.CRITICAL: logging.CRITICAL,
}


class PythonLoggingReporter:
    """Write structured Claviger reports through Python's logging system."""

    def __init__(
        self,
        logger: logging.Logger | None = None,
    ) -> None:
        self.logger = logger or logging.getLogger("claviger")

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Write a structured report event to the configured logger."""
        level = SEVERITY_LEVELS[event.severity]

        message = (
            f"[{event.event_type}] "
            f"{event.title} — {event.summary}"
        )

        if event.details is not None:
            message += f"\nDetails: {event.details}"

        context: list[str] = []

        if event.guild_id is not None:
            context.append(
                f"guild_id={event.guild_id}"
            )

        if event.actor_id is not None:
            context.append(
                f"actor_id={event.actor_id}"
            )

        if event.target_id is not None:
            context.append(
                f"target_id={event.target_id}"
            )

        if context:
            message += (
                "\nContext: "
                + ", ".join(context)
            )

        self.logger.log(
            level,
            message,
        )