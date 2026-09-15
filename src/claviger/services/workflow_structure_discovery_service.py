import discord

from claviger.models.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.services.role_discovery import RoleDiscoveryService


class WorkflowStructureDiscoveryService:
    """Observe Discord resources and recognize compatible workflow structures."""

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
                "The application could not resolve its own member in the guild."
            )

        # Role hierarchy already has one authoritative implementation.
        # Reusing it also gives workflow discovery the application's Discord role
        # without relying on any role name.
        hierarchy = await self.role_discovery_service.get_hierarchy(
            guild,
        )

        application_role = hierarchy.bot_role

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
                        application_role=application_role,
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

        workflow_candidates = self._discover_workflow_candidates(
            categories=categories,
            text_channels=text_channels,
        )

        # Creation permissions remain capabilities rather than discovery
        # decisions. Existing resources can still be proposed even when the
        # application is currently unable to create new ones.
        guild_permissions = bot_member.guild_permissions

        return WorkflowStructureDiscoveryResult(
            categories=categories,
            text_channels=text_channels,
            manageable_roles=manageable_roles,
            workflow_candidates=workflow_candidates,
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
        application_role: discord.Role,
    ) -> WorkflowTextChannelCandidate:
        """Build one immutable text-channel snapshot and explicit role overwrite."""

        everyone_permissions = channel.permissions_for(
            guild.default_role,
        )

        bot_permissions = channel.permissions_for(
            bot_member,
        )

        application_role_overwrite = channel.overwrites_for(
            application_role,
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
            application_role_send_override=(application_role_overwrite.send_messages),
        )

    @staticmethod
    def _discover_workflow_candidates(
        *,
        categories: tuple[WorkflowCategoryCandidate, ...],
        text_channels: tuple[WorkflowTextChannelCandidate, ...],
    ) -> tuple[WorkflowStructureCandidate, ...]:
        """Recognize workflow structures from permissions without name inference.

        A category is a workflow candidate when it contains:

        - at least one protected channel where @everyone cannot send messages
          and the application's role explicitly can;
        - at least one interactive channel where @everyone can send messages.

        Several protected or interactive channels do not invalidate the
        candidate. They simply require a later explicit human selection.
        """

        candidates: list[WorkflowStructureCandidate] = []

        for category in categories:
            category_channels = tuple(
                channel
                for channel in text_channels
                if channel.category_id == category.category_id
            )

            protected_channels = tuple(
                channel
                for channel in category_channels
                if (
                    not channel.everyone_can_send
                    and channel.application_role_send_override is True
                    and channel.bot_can_send
                )
            )

            interactive_channels = tuple(
                channel for channel in category_channels if channel.everyone_can_send
            )

            if not protected_channels or not interactive_channels:
                continue

            candidates.append(
                WorkflowStructureCandidate(
                    category=category,
                    protected_channels=protected_channels,
                    interactive_channels=interactive_channels,
                )
            )

        return tuple(candidates)
