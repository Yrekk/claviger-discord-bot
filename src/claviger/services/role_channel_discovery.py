import discord

from claviger.models.role_channel_discovery import RoleChannelDiscovery


class RoleChannelDiscoveryService:
    """Discover Discord role-to-channel mappings for a catalog prefix."""

    def discover(
        self,
        guild: discord.Guild,
        *,
        prefix: str,
    ) -> list[RoleChannelDiscovery]:
        """Build a complete catalog discovery snapshot from Discord."""

        if not prefix:
            raise ValueError("Catalog role prefix cannot be empty.")

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger member could not be resolved in the guild.")

        discoveries: list[RoleChannelDiscovery] = []

        for role in guild.roles:
            catalog_key = self._extract_catalog_key(
                role.name,
                prefix,
            )

            if catalog_key is None:
                continue

            channels = self._find_explicit_channels(
                guild,
                role,
            )

            mapping_valid = len(channels) == 1

            channel = channels[0] if mapping_valid else None

            discoveries.append(
                RoleChannelDiscovery(
                    role_id=role.id,
                    role_name=role.name,
                    catalog_key=catalog_key,
                    role_manageable=role < bot_member.top_role,
                    channel_id=(channel.id if channel is not None else None),
                    channel_name=(channel.name if channel is not None else None),
                    channel_present=channel is not None,
                    mapping_valid=mapping_valid,
                )
            )

        return discoveries

    @staticmethod
    def _extract_catalog_key(
        role_name: str,
        prefix: str,
    ) -> str | None:
        """Return the role key when its name matches the catalog prefix."""

        if not role_name.startswith(prefix):
            return None

        catalog_key = role_name[len(prefix) :].strip()

        if not catalog_key:
            return None

        return catalog_key

    @staticmethod
    def _find_explicit_channels(
        guild: discord.Guild,
        role: discord.Role,
    ) -> list[discord.TextChannel | discord.ForumChannel]:
        """Return content channels explicitly visible to the role."""

        channels: list[discord.TextChannel | discord.ForumChannel] = []

        for channel in guild.channels:
            if not isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.ForumChannel,
                ),
            ):
                continue

            overwrite = channel.overwrites_for(
                role,
            )

            if overwrite.view_channel is True:
                channels.append(
                    channel,
                )

        return channels
