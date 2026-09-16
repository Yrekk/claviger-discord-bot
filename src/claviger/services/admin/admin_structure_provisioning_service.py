import discord

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)

DEFAULT_ADMIN_CATEGORY_NAME = "Claviger Admin"
DEFAULT_COMMAND_CHANNEL_NAME = "commands"
DEFAULT_ACTIVITY_FORUM_NAME = "activity"
DEFAULT_ERROR_FORUM_NAME = "errors"
DEFAULT_UNASSIGNED_REPORT_FORUM_NAME = "reporting"
PROVISIONING_REASON = "Claviger administrative structure provisioning"


class AdminStructureProvisioningPermissionError(RuntimeError):
    """Raised when Claviger cannot safely mutate Discord channel structure."""


class AdminStructureProvisioningService:
    """Apply safe Discord mutations requested by ADMIN reconciliation."""

    async def provision(
        self,
        *,
        guild: discord.Guild,
        reconciliation: AdminConfigurationReconciliationResult,
        configuration: GuildAdminConfiguration | None,
    ) -> AdminStructureProvisioningResult:
        """Apply the structural action selected by reconciliation."""

        if configuration is not None and configuration.guild_id != guild.id:
            raise ValueError(
                "Administrative configuration belongs to another Discord guild."
            )

        decision = reconciliation.decision

        if decision in {
            AdminConfigurationReconciliationDecision.KEEP,
            AdminConfigurationReconciliationDecision.IMPORT,
            AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
        }:
            return AdminStructureProvisioningResult(
                guild_id=guild.id,
                decision=decision,
                category_id=(
                    reconciliation.category.category_id
                    if reconciliation.category is not None
                    else None
                ),
                configuration=(
                    configuration
                    if decision == AdminConfigurationReconciliationDecision.KEEP
                    else None
                ),
            )

        if decision == AdminConfigurationReconciliationDecision.CREATE:
            return await self._create_default_structure(
                guild=guild,
            )

        if decision == AdminConfigurationReconciliationDecision.COMPLETE:
            return await self._complete_existing_structure(
                guild=guild,
                reconciliation=reconciliation,
                configuration=configuration,
            )

        raise RuntimeError(f"Unsupported reconciliation decision: {decision!r}.")

    async def _create_default_structure(
        self,
        *,
        guild: discord.Guild,
    ) -> AdminStructureProvisioningResult:
        """Create one complete private ADMIN structure with deterministic routing."""

        bot_member = self._require_manage_channels(guild)

        overwrites = self._build_private_overwrites(
            guild=guild,
            bot_member=bot_member,
        )

        category = await guild.create_category(
            DEFAULT_ADMIN_CATEGORY_NAME,
            overwrites=overwrites,
            reason=PROVISIONING_REASON,
        )

        command_channel = await guild.create_text_channel(
            DEFAULT_COMMAND_CHANNEL_NAME,
            category=category,
            overwrites=overwrites,
            reason=PROVISIONING_REASON,
        )

        activity_forum = await guild.create_forum(
            DEFAULT_ACTIVITY_FORUM_NAME,
            category=category,
            overwrites=overwrites,
            reason=PROVISIONING_REASON,
        )

        error_forum = await guild.create_forum(
            DEFAULT_ERROR_FORUM_NAME,
            category=category,
            overwrites=overwrites,
            reason=PROVISIONING_REASON,
        )

        configuration = GuildAdminConfiguration(
            guild_id=guild.id,
            category_id=category.id,
            activity_forum_id=activity_forum.id,
            command_channel_id=command_channel.id,
            error_forum_id=error_forum.id,
        )

        return AdminStructureProvisioningResult(
            guild_id=guild.id,
            decision=AdminConfigurationReconciliationDecision.CREATE,
            category_id=category.id,
            created_category=True,
            created_channel_ids=(
                command_channel.id,
                activity_forum.id,
                error_forum.id,
            ),
            configuration=configuration,
        )

    async def _complete_existing_structure(
        self,
        *,
        guild: discord.Guild,
        reconciliation: AdminConfigurationReconciliationResult,
        configuration: GuildAdminConfiguration | None,
    ) -> AdminStructureProvisioningResult:
        """Repair one selected ADMIN category without destructive replacement."""

        candidate = reconciliation.category

        if candidate is None:
            raise RuntimeError(
                "COMPLETE reconciliation requires one selected admin category."
            )

        bot_member = self._require_manage_channels(guild)

        category = self._find_category(
            guild,
            category_id=candidate.category_id,
        )

        if category is None:
            raise RuntimeError(
                "The reconciled administrative category disappeared before "
                "provisioning."
            )

        (
            category_permissions_repaired,
            repaired_channel_ids,
        ) = await self._repair_category_permissions(
            guild=guild,
            category=category,
            bot_member=bot_member,
        )

        created_channel_ids: list[int] = []

        if configuration is None:
            await self._complete_unconfigured_shape(
                guild=guild,
                category=category,
                bot_member=bot_member,
                created_channel_ids=created_channel_ids,
            )

            return AdminStructureProvisioningResult(
                guild_id=guild.id,
                decision=AdminConfigurationReconciliationDecision.COMPLETE,
                category_id=category.id,
                created_channel_ids=tuple(created_channel_ids),
                category_permissions_repaired=category_permissions_repaired,
                repaired_channel_ids=repaired_channel_ids,
                configuration=None,
            )

        if configuration.category_id != category.id:
            raise ValueError(
                "Administrative configuration does not reference the reconciled "
                "category."
            )

        resolved_configuration = await self._complete_configured_routing(
            guild=guild,
            category=category,
            bot_member=bot_member,
            configuration=configuration,
            created_channel_ids=created_channel_ids,
        )

        return AdminStructureProvisioningResult(
            guild_id=guild.id,
            decision=AdminConfigurationReconciliationDecision.COMPLETE,
            category_id=category.id,
            created_channel_ids=tuple(created_channel_ids),
            category_permissions_repaired=category_permissions_repaired,
            repaired_channel_ids=repaired_channel_ids,
            configuration=resolved_configuration,
        )

    async def _complete_unconfigured_shape(
        self,
        *,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
        created_channel_ids: list[int],
    ) -> None:
        """Create only the missing structural channel types without semantic mapping."""

        text_channels = [
            channel
            for channel in category.channels
            if isinstance(channel, discord.TextChannel)
        ]

        forum_channels = [
            channel
            for channel in category.channels
            if isinstance(channel, discord.ForumChannel)
        ]

        used_names = {channel.name.casefold() for channel in category.channels}

        if not text_channels:
            command_channel = await self._create_text_channel(
                guild=guild,
                category=category,
                bot_member=bot_member,
                name=self._next_available_name(
                    used_names,
                    DEFAULT_COMMAND_CHANNEL_NAME,
                ),
            )

            created_channel_ids.append(command_channel.id)
            used_names.add(command_channel.name.casefold())

        missing_forum_count = max(
            0,
            2 - len(forum_channels),
        )

        for _ in range(missing_forum_count):
            forum = await self._create_forum_channel(
                guild=guild,
                category=category,
                bot_member=bot_member,
                name=self._next_available_name(
                    used_names,
                    DEFAULT_UNASSIGNED_REPORT_FORUM_NAME,
                ),
            )

            created_channel_ids.append(forum.id)
            used_names.add(forum.name.casefold())

    async def _complete_configured_routing(
        self,
        *,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
        configuration: GuildAdminConfiguration,
        created_channel_ids: list[int],
    ) -> GuildAdminConfiguration:
        """Preserve configured routing and recreate only missing destinations."""

        command_channel = self._find_typed_child(
            category,
            channel_id=configuration.command_channel_id,
            expected_type=discord.TextChannel,
        )

        if command_channel is None:
            command_channel = await self._create_text_channel(
                guild=guild,
                category=category,
                bot_member=bot_member,
                name=self._next_available_channel_name(
                    category,
                    DEFAULT_COMMAND_CHANNEL_NAME,
                ),
            )

            created_channel_ids.append(command_channel.id)

        activity_forum = self._find_typed_child(
            category,
            channel_id=configuration.activity_forum_id,
            expected_type=discord.ForumChannel,
        )

        if activity_forum is None:
            activity_forum = await self._create_forum_channel(
                guild=guild,
                category=category,
                bot_member=bot_member,
                name=self._next_available_channel_name(
                    category,
                    DEFAULT_ACTIVITY_FORUM_NAME,
                ),
            )

            created_channel_ids.append(activity_forum.id)

        error_channel_id = configuration.error_forum_id

        if error_channel_id == configuration.activity_forum_id:
            error_channel_id = None

        error_forum = self._find_typed_child(
            category,
            channel_id=error_channel_id,
            expected_type=discord.ForumChannel,
        )

        if error_forum is None or error_forum.id == activity_forum.id:
            error_forum = await self._create_forum_channel(
                guild=guild,
                category=category,
                bot_member=bot_member,
                name=self._next_available_channel_name(
                    category,
                    DEFAULT_ERROR_FORUM_NAME,
                ),
            )

            created_channel_ids.append(error_forum.id)

        return GuildAdminConfiguration(
            guild_id=configuration.guild_id,
            category_id=category.id,
            activity_forum_id=activity_forum.id,
            command_channel_id=command_channel.id,
            error_forum_id=error_forum.id,
        )

    async def _repair_category_permissions(
        self,
        *,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
    ) -> tuple[bool, tuple[int, ...]]:
        """Hide ADMIN from @everyone and restore the bot's required access."""

        category_changed = False
        repaired_channel_ids: list[int] = []

        if await self._ensure_everyone_hidden(
            channel=category,
            default_role=guild.default_role,
        ):
            category_changed = True

        if await self._ensure_bot_access(
            channel=category,
            bot_member=bot_member,
        ):
            category_changed = True

        for channel in category.channels:
            child_changed = await self._ensure_everyone_hidden(
                channel=channel,
                default_role=guild.default_role,
            )

            if isinstance(
                channel,
                (
                    discord.TextChannel,
                    discord.ForumChannel,
                ),
            ):
                child_changed = (
                    await self._ensure_bot_access(
                        channel=channel,
                        bot_member=bot_member,
                    )
                    or child_changed
                )

            if child_changed:
                repaired_channel_ids.append(channel.id)

        return (
            category_changed,
            tuple(repaired_channel_ids),
        )

    async def _ensure_everyone_hidden(
        self,
        *,
        channel: discord.abc.GuildChannel,
        default_role: discord.Role,
    ) -> bool:
        """Deny @everyone visibility while preserving its other overwrite values."""

        if not channel.permissions_for(default_role).view_channel:
            return False

        overwrite = channel.overwrites_for(
            default_role,
        )

        overwrite.view_channel = False

        await channel.set_permissions(
            default_role,
            overwrite=overwrite,
            reason=PROVISIONING_REASON,
        )

        return True

    async def _ensure_bot_access(
        self,
        *,
        channel: discord.abc.GuildChannel,
        bot_member: discord.Member,
    ) -> bool:
        """Restore the effective permissions required by ADMIN channels."""

        permissions = channel.permissions_for(
            bot_member,
        )

        if permissions.view_channel and permissions.send_messages:
            return False

        overwrite = channel.overwrites_for(
            bot_member,
        )

        overwrite.view_channel = True
        overwrite.send_messages = True

        await channel.set_permissions(
            bot_member,
            overwrite=overwrite,
            reason=PROVISIONING_REASON,
        )

        return True

    async def _create_text_channel(
        self,
        *,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
        name: str,
    ) -> discord.TextChannel:
        """Create one private administrative text channel."""

        return await guild.create_text_channel(
            name,
            category=category,
            overwrites=self._build_private_overwrites(
                guild=guild,
                bot_member=bot_member,
            ),
            reason=PROVISIONING_REASON,
        )

    async def _create_forum_channel(
        self,
        *,
        guild: discord.Guild,
        category: discord.CategoryChannel,
        bot_member: discord.Member,
        name: str,
    ) -> discord.ForumChannel:
        """Create one private administrative forum channel."""

        return await guild.create_forum(
            name,
            category=category,
            overwrites=self._build_private_overwrites(
                guild=guild,
                bot_member=bot_member,
            ),
            reason=PROVISIONING_REASON,
        )

    @staticmethod
    def _build_private_overwrites(
        *,
        guild: discord.Guild,
        bot_member: discord.Member,
    ) -> dict[
        discord.Role | discord.Member,
        discord.PermissionOverwrite,
    ]:
        """Build minimal private ADMIN overwrites for new Discord channels."""

        return {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
            ),
        }

    @staticmethod
    def _require_manage_channels(
        guild: discord.Guild,
    ) -> discord.Member:
        """Return the bot member when Discord structural mutation is permitted."""

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger member could not be resolved in the guild.")

        if not bot_member.guild_permissions.manage_channels:
            raise AdminStructureProvisioningPermissionError(
                "Claviger requires the Manage Channels permission for "
                "ADMIN provisioning."
            )

        return bot_member

    @staticmethod
    def _find_category(
        guild: discord.Guild,
        *,
        category_id: int,
    ) -> discord.CategoryChannel | None:
        """Resolve one current Discord category by persisted identity."""

        return next(
            (
                channel
                for channel in guild.channels
                if isinstance(
                    channel,
                    discord.CategoryChannel,
                )
                and channel.id == category_id
            ),
            None,
        )

    @staticmethod
    def _find_typed_child(
        category: discord.CategoryChannel,
        *,
        channel_id: int | None,
        expected_type: (type[discord.TextChannel] | type[discord.ForumChannel]),
    ) -> discord.TextChannel | discord.ForumChannel | None:
        """Resolve one configured child only when its Discord type still matches."""

        if channel_id is None:
            return None

        return next(
            (
                channel
                for channel in category.channels
                if channel.id == channel_id
                and isinstance(
                    channel,
                    expected_type,
                )
            ),
            None,
        )

    @classmethod
    def _next_available_channel_name(
        cls,
        category: discord.CategoryChannel,
        base_name: str,
    ) -> str:
        """Return a readable unused default name without treating names as identity."""

        return cls._next_available_name(
            {channel.name.casefold() for channel in category.channels},
            base_name,
        )

    @staticmethod
    def _next_available_name(
        used_names: set[str],
        base_name: str,
    ) -> str:
        """Return one unused Discord channel name from a cosmetic base name."""

        normalized_base = base_name.casefold()

        if normalized_base not in used_names:
            return base_name

        suffix = 2

        while f"{normalized_base}-{suffix}" in used_names:
            suffix += 1

        return f"{base_name}-{suffix}"
