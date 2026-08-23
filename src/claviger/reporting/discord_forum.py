import discord

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)


SEVERITY_COLORS = {
    ReportSeverity.INFO: discord.Color.blue(),
    ReportSeverity.WARNING: discord.Color.orange(),
    ReportSeverity.ERROR: discord.Color.red(),
    ReportSeverity.CRITICAL: discord.Color.dark_red(),
}


class DiscordForumReporter:
    """Publish structured administrative reports to a Discord forum."""

    def __init__(
        self,
        client: discord.Client,
        forum_channel_id: int,
    ) -> None:
        self.client = client
        self.forum_channel_id = forum_channel_id

    async def report(
        self,
        event: ReportEvent,
    ) -> None:
        """Publish one structured event as a Discord forum post."""
        forum = await self._get_forum()

        embed = self._create_embed(
            event,
        )

        thread_name = (
            f"[{event.severity.value.upper()}] "
            f"{event.title}"
        )[:100]

        await forum.create_thread(
            name=thread_name,
            embed=embed,
        )

    async def _get_forum(
        self,
    ) -> discord.ForumChannel:
        """Resolve the configured report forum from cache or Discord."""
        channel = self.client.get_channel(
            self.forum_channel_id,
        )

        if channel is None:
            channel = await self.client.fetch_channel(
                self.forum_channel_id,
            )

        if not isinstance(
            channel,
            discord.ForumChannel,
        ):
            raise RuntimeError(
                (
                    "Administrative report channel "
                    f"{self.forum_channel_id} is not a Discord forum."
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