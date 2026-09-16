import discord

from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.reporter import ReporterUnavailableError
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

SEVERITY_COLORS = {
    ReportSeverity.INFO: discord.Color.blue(),
    ReportSeverity.WARNING: discord.Color.orange(),
    ReportSeverity.ERROR: discord.Color.red(),
    ReportSeverity.CRITICAL: discord.Color.dark_red(),
}


class DiscordForumReporter:
    """Publish structured reports to guild-specific administrative forums.

    Discord routing is resolved from the guild's persisted ADMIN configuration
    for every event. No application-wide Discord forum is assumed.

    Routing invariant:
        INFO events are operational activity and go to ``activity_forum_id``.
        WARNING, ERROR and CRITICAL events are incidents and go to
        ``error_forum_id``.
    """

    def __init__(
        self,
        client: discord.Client,
        repository: GuildAdminConfigurationRepository,
    ) -> None:
        """Create a DB-backed Discord forum reporter."""

        self.client = client
        self.repository = repository

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Publish one structured event in its guild-specific report forum."""

        guild_id = event.guild_id

        if guild_id is None:
            raise RuntimeError(
                "Discord forum reporting requires a guild-scoped ReportEvent."
            )

        configuration = await self.repository.get(
            guild_id,
        )

        if configuration is None:
            raise ReporterUnavailableError(
                "Discord forum reporting is unavailable because guild "
                f"{guild_id} has no ADMIN configuration yet."
            )

        forum_channel_id = self._resolve_forum_channel_id(
            configuration,
            event.severity,
        )

        forum = await self._get_forum(
            forum_channel_id,
        )

        embed = self._create_embed(
            event,
        )

        thread_name = (f"[{event.severity.value.upper()}] {event.title}")[:100]

        await forum.create_thread(
            name=thread_name,
            embed=embed,
        )

    @staticmethod
    def _resolve_forum_channel_id(
        configuration: GuildAdminConfiguration,
        severity: ReportSeverity,
    ) -> int:
        """Resolve the correct forum for one guild and report severity."""

        if severity == ReportSeverity.INFO:
            return configuration.activity_forum_id

        error_forum_id = configuration.error_forum_id

        if error_forum_id is None:
            raise ReporterUnavailableError(
                "Discord incident reporting is unavailable because guild "
                f"{configuration.guild_id} has no error forum configured yet."
            )

        return error_forum_id

    async def _get_forum(
        self,
        forum_channel_id: int,
    ) -> discord.ForumChannel:
        """Resolve one report forum from cache or Discord."""

        channel = self.client.get_channel(
            forum_channel_id,
        )

        if channel is None:
            channel = await self.client.fetch_channel(
                forum_channel_id,
            )

        if not isinstance(
            channel,
            discord.ForumChannel,
        ):
            raise RuntimeError(
                (
                    "Administrative report channel "
                    f"{forum_channel_id} is not a Discord forum."
                )
            )

        return channel

    @staticmethod
    def _create_embed(
        event: ReportEvent,
    ) -> discord.Embed:
        """Build the Discord representation of a structured report."""

        embed = discord.Embed(
            title=event.title,
            description=event.summary,
            color=SEVERITY_COLORS[event.severity],
            timestamp=event.occurred_at,
        )

        embed.add_field(
            name="Événement",
            value=f"`{event.event_type}`",
            inline=False,
        )

        embed.add_field(
            name="Sévérité",
            value=event.severity.value.upper(),
            inline=True,
        )

        if event.guild_label is not None:
            embed.add_field(
                name="Serveur",
                value=event.guild_label,
                inline=True,
            )

        if event.actor_label is not None:
            embed.add_field(
                name="Acteur",
                value=event.actor_label,
                inline=True,
            )

        if event.target_label is not None:
            embed.add_field(
                name="Cible",
                value=event.target_label,
                inline=True,
            )

        if event.details is not None:
            embed.add_field(
                name="Détails",
                value=event.details[:1024],
                inline=False,
            )

        embed.set_footer(
            text="Claviger · Rapport système",
        )

        return embed
