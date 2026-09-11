import discord

from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminChannelType,
    AdminStructureDiscoveryResult,
)


class AdminStructureDiscoveryService:
    """Discover possible administrative Discord structures without mutation."""

    def discover(
        self,
        guild: discord.Guild,
        *,
        configured_category_id: int | None = None,
    ) -> AdminStructureDiscoveryResult:
        """Observe administrative category candidates in one Discord guild."""

        if configured_category_id is not None and configured_category_id <= 0:
            raise ValueError("Configured admin category ID must be greater than zero.")

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger member could not be resolved in the guild.")

        default_role = guild.default_role

        categories = tuple(
            self._build_category_candidate(
                category=channel,
                default_role=default_role,
                bot_member=bot_member,
            )
            for channel in guild.channels
            if isinstance(
                channel,
                discord.CategoryChannel,
            )
            and (
                self._matches_admin_category(
                    channel.name,
                )
                or channel.id == configured_category_id
            )
        )

        return AdminStructureDiscoveryResult(
            categories=categories,
        )

    def _build_category_candidate(
        self,
        *,
        category: discord.CategoryChannel,
        default_role: discord.Role,
        bot_member: discord.Member,
    ) -> AdminCategoryCandidate:
        """Build one immutable snapshot of an administrative category."""

        everyone_permissions = category.permissions_for(
            default_role,
        )

        bot_permissions = category.permissions_for(
            bot_member,
        )

        has_public_child = any(
            channel.permissions_for(
                default_role,
            ).view_channel
            for channel in category.channels
        )

        channels = tuple(
            self._build_channel_candidate(
                channel=channel,
                default_role=default_role,
                bot_member=bot_member,
            )
            for channel in category.channels
            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.ForumChannel,
                ),
            )
        )

        return AdminCategoryCandidate(
            category_id=category.id,
            category_name=category.name,
            everyone_can_view=bool(
                everyone_permissions.view_channel,
            ),
            bot_can_view=bool(
                bot_permissions.view_channel,
            ),
            has_public_child=has_public_child,
            channels=channels,
        )

    def _build_channel_candidate(
        self,
        *,
        channel: discord.TextChannel | discord.ForumChannel,
        default_role: discord.Role,
        bot_member: discord.Member,
    ) -> AdminChannelCandidate:
        """Build one supported administrative channel snapshot."""

        everyone_permissions = channel.permissions_for(
            default_role,
        )

        bot_permissions = channel.permissions_for(
            bot_member,
        )

        channel_type: AdminChannelType

        if isinstance(
            channel,
            discord.ForumChannel,
        ):
            channel_type = "forum"

        else:
            channel_type = "text"

        return AdminChannelCandidate(
            channel_id=channel.id,
            channel_name=channel.name,
            channel_type=channel_type,
            everyone_can_view=bool(
                everyone_permissions.view_channel,
            ),
            bot_can_view=bool(
                bot_permissions.view_channel,
            ),
            bot_can_send=bool(
                bot_permissions.send_messages,
            ),
        )

    @staticmethod
    def _matches_admin_category(
        category_name: str,
    ) -> bool:
        """Return whether a category name identifies an admin candidate."""

        return "admin" in category_name.casefold()
