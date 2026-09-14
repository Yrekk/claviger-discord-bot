import discord

from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.repositories.guild_admin_configuration_repository import (
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
        """Create a DB-backed Discord forum reporter.

        Args:
            client:
                Authenticated Discord client used to resolve forum channels.

            repository:
                Guild ADMIN configuration repository used to resolve the
                destination belonging to the event's guild.
        """

        self.client = client
        self.repository = repository

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Publish one structured event in its guild-specific report forum.

        Args:
            event:
                Structured report carrying the guild context required for
                Discord routing.

        Raises:
            RuntimeError:
                If the event has no guild ID, no ADMIN configuration exists for
                the guild, an incident has no configured error forum, or the
                configured Discord destination is not a forum.

            Database errors:
                Propagated when ADMIN configuration cannot be read.

            Discord errors:
                Propagated when the destination cannot be fetched or written.
        """

        guild_id = event.guild_id

        if guild_id is None:
            raise RuntimeError(
                "Discord forum reporting requires a guild-scoped ReportEvent."
            )

        configuration = await self.repository.get(
            guild_id,
        )

        if configuration is None:
            raise RuntimeError(
                "Discord forum reporting is unavailable because guild "
                f"{guild_id} has no ADMIN configuration."
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
        """Resolve the correct forum for one guild and report severity.

        Args:
            configuration:
                Persisted ADMIN routing for the event's guild.

            severity:
                Event severity used to distinguish normal activity from an
                incident.

        Returns:
            int:
                Discord forum channel ID belonging to the same guild.

        Raises:
            RuntimeError:
                If an incident must be routed but the guild has no configured
                error forum.
        """

        if severity == ReportSeverity.INFO:
            return configuration.activity_forum_id

        error_forum_id = configuration.error_forum_id

        if error_forum_id is None:
            raise RuntimeError(
                "Discord incident reporting is unavailable because guild "
                f"{configuration.guild_id} has no error forum configured."
            )

        return error_forum_id

    async def _get_forum(
        self,
        forum_channel_id: int,
    ) -> discord.ForumChannel:
        """Resolve one report forum from cache or Discord.

        Args:
            forum_channel_id:
                Discord channel ID selected from the guild's ADMIN
                configuration.

        Returns:
            discord.ForumChannel:
                Validated Discord forum destination.

        Raises:
            RuntimeError:
                If the configured channel is not a Discord forum.
        """

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
