import discord

from claviger.models.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.services.role_discovery import RoleDiscoveryService


class WorkflowStructureDiscoveryService:
    """Observe Discord resources that can participate in workflow configuration."""

    def __init__(
        self,
        role_discovery_service: RoleDiscoveryService,
    ) -> None:
        self.role_discovery_service = role_discovery_service

    async def discover(
        self,
        guild: discord.Guild,
    ) -> WorkflowStructureDiscoveryResult:
        """Return one immutable workflow-configuration snapshot without mutation."""

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError(
                "Claviger could not resolve its own member in the guild."
            )

        # Role manageability already has one authoritative implementation in
        # Claviger. Reusing it prevents workflow configuration from inventing a
        # second and potentially inconsistent hierarchy rule.
        hierarchy = await self.role_discovery_service.get_hierarchy(
            guild,
        )

        categories = tuple(
            sorted(
                (
                    self._build_category_candidate(
                        category=channel,
                        guild=guild,
                        bot_member=bot_member,
                    )
                    for channel in guild.channels
                    if isinstance(
                        channel,
                        discord.CategoryChannel,
                    )
                ),
                key=lambda candidate: (
                    candidate.category_name.casefold(),
                    candidate.category_id,
                ),
            )
        )

        text_channels = tuple(
            sorted(
                (
                    self._build_text_channel_candidate(
                        channel=channel,
                        guild=guild,
                        bot_member=bot_member,
                    )
                    for channel in guild.channels
                    if isinstance(
                        channel,
                        discord.TextChannel,
                    )
                ),
                key=lambda candidate: (
                    candidate.channel_name.casefold(),
                    candidate.channel_id,
                ),
            )
        )

        manageable_roles = tuple(
            WorkflowRoleCandidate(
                role_id=role.id,
                role_name=role.name,
            )
            for role in hierarchy.manageable_roles
        )

        # Creation permissions are deliberately exposed as capabilities rather
        # than mixed into the candidate lists. Existing resources may still be
        # imported even when Claviger is not allowed to create new ones.
        guild_permissions = bot_member.guild_permissions

        return WorkflowStructureDiscoveryResult(
            categories=categories,
            text_channels=text_channels,
            manageable_roles=manageable_roles,
            can_create_channels=bool(
                guild_permissions.manage_channels,
            ),
            can_create_roles=bool(
                guild_permissions.manage_roles,
            ),
        )

    @staticmethod
    def _build_category_candidate(
        *,
        category: discord.CategoryChannel,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> WorkflowCategoryCandidate:
        """Build one immutable category snapshot from effective permissions."""

        everyone_permissions = category.permissions_for(
            guild.default_role,
        )

        bot_permissions = category.permissions_for(
            bot_member,
        )

        return WorkflowCategoryCandidate(
            category_id=category.id,
            category_name=category.name,
            everyone_can_view=bool(
                everyone_permissions.view_channel,
            ),
            bot_can_view=bool(
                bot_permissions.view_channel,
            ),
        )

    @staticmethod
    def _build_text_channel_candidate(
        *,
        channel: discord.TextChannel,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> WorkflowTextChannelCandidate:
        """Build one immutable text-channel snapshot from effective permissions."""

        everyone_permissions = channel.permissions_for(
            guild.default_role,
        )

        bot_permissions = channel.permissions_for(
            bot_member,
        )

        return WorkflowTextChannelCandidate(
            channel_id=channel.id,
            channel_name=channel.name,
            category_id=channel.category_id,
            everyone_can_view=bool(
                everyone_permissions.view_channel,
            ),
            everyone_can_send=bool(
                everyone_permissions.send_messages,
            ),
            bot_can_view=bool(
                bot_permissions.view_channel,
            ),
            bot_can_send=bool(
                bot_permissions.send_messages,
            ),
        )
