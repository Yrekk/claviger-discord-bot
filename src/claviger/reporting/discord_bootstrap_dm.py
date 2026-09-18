import discord

from claviger.database.connection import DatabaseUnavailableError
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.reporter import ReporterUnavailableError
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

INCIDENT_COLORS = {
    ReportSeverity.WARNING: discord.Color.orange(),
    ReportSeverity.ERROR: discord.Color.red(),
    ReportSeverity.CRITICAL: discord.Color.dark_red(),
}


class DiscordBootstrapDMReporter:
    """Send actor-scoped incidents by DM until ADMIN routing is operational."""

    def __init__(
        self,
        client: discord.Client,
        repository: GuildAdminConfigurationRepository,
    ) -> None:
        self.client = client
        self.repository = repository

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Send one bootstrap incident directly to the actor who triggered it."""

        if event.severity == ReportSeverity.INFO:
            # INFO is normal operational traffic for the ADMIN activity forum,
            # not a bootstrap incident. This reporter is simply not applicable.
            return

        if event.guild_id is None:
            raise ReporterUnavailableError(
                "Bootstrap DM reporting requires a guild-scoped event."
            )

        if event.actor_id is None:
            raise ReporterUnavailableError(
                "Bootstrap DM reporting requires an actor-scoped event."
            )

        try:
            configuration = await self.repository.get(
                event.guild_id,
            )
        except DatabaseUnavailableError:
            # If persistence itself is unavailable, ADMIN routing cannot be
            # trusted. The actor DM remains the safest Discord fallback.
            configuration = None

        if configuration is not None and configuration.is_complete:
            # Normal ADMIN reporting has taken over. Silently decline instead
            # of producing one warning for every successfully routed incident.
            return

        user = self.client.get_user(
            event.actor_id,
        )

        if user is None:
            user = await self.client.fetch_user(
                event.actor_id,
            )

        await user.send(
            embed=self._create_embed(
                event,
            )
        )

    @staticmethod
    def _create_embed(
        event: ReportEvent,
    ) -> discord.Embed:
        """Render one compact bootstrap incident for a direct message."""

        embed = discord.Embed(
            title=event.title,
            description=event.summary,
            color=INCIDENT_COLORS[event.severity],
            timestamp=event.occurred_at,
        )

        if event.guild_label is not None:
            embed.add_field(
                name="Serveur",
                value=event.guild_label,
                inline=False,
            )

        embed.add_field(
            name="Événement",
            value=f"`{event.event_type}`",
            inline=False,
        )

        if event.details is not None:
            embed.add_field(
                name="Détails",
                value=event.details[:1024],
                inline=False,
            )

        embed.set_footer(
            text="Claviger · Incident de bootstrap",
        )

        return embed
