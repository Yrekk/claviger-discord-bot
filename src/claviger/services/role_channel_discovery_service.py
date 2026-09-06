import discord

from claviger.models.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)


class RoleChannelDiscoveryService:
    """Build a complete Discord role-to-channel snapshot."""

    def build_snapshot(
        self,
        guild: discord.Guild,
    ) -> GuildRoleChannelSnapshot:
        """Observe every role and supported content channel in the guild."""

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger member could not be resolved in the guild.")

        content_channels = tuple(
            channel
            for channel in guild.channels
            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.ForumChannel,
                ),
            )
        )

        channel_snapshots = tuple(
            DiscordChannelSnapshot(
                channel_id=channel.id,
                channel_name=channel.name,
            )
            for channel in content_channels
        )

        role_snapshots = tuple(
            DiscordRoleSnapshot(
                role_id=role.id,
                role_name=role.name,
                role_manageable=role < bot_member.top_role,
                explicit_channel_ids=tuple(
                    channel.id
                    for channel in content_channels
                    if channel.overwrites_for(role).view_channel is True
                ),
            )
            for role in guild.roles
        )

        return GuildRoleChannelSnapshot(
            roles=role_snapshots,
            channels=channel_snapshots,
        )
