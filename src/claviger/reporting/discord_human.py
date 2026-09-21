import logging

from claviger.reporting.discord_bootstrap_dm import DiscordBootstrapDMReporter
from claviger.reporting.discord_forum import DiscordForumReporter
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.reporter import ReporterUnavailableError


class DiscordHumanReporter:
    """Route Discord reports to ADMIN first, then DM incidents on failure."""

    def __init__(
        self,
        *,
        forum_reporter: DiscordForumReporter,
        fallback_dm_reporter: DiscordBootstrapDMReporter,
        logger: logging.Logger | None = None,
    ) -> None:
        self.forum_reporter = forum_reporter
        self.fallback_dm_reporter = fallback_dm_reporter
        self.logger = logger or logging.getLogger(__name__)

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Use ADMIN forums when healthy and actor DM when incident routing fails."""

        try:
            await self.forum_reporter.report(
                event,
            )
            return

        except Exception as forum_error:
            if event.severity is ReportSeverity.INFO:
                raise

            try:
                await self.fallback_dm_reporter.report(
                    event,
                    force=True,
                )

            except Exception as fallback_error:
                raise ReporterUnavailableError(
                    "Discord ADMIN reporting failed and incident DM fallback "
                    "was also unavailable."
                ) from fallback_error

            self.logger.warning(
                "Discord ADMIN reporting failed for event %s; "
                "actor DM fallback delivered instead: %s: %s",
                event.event_type,
                type(forum_error).__name__,
                forum_error,
            )
