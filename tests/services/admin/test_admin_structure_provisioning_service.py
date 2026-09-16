from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.services.admin.admin_structure_provisioning_service import (
    AdminStructureProvisioningPermissionError,
    AdminStructureProvisioningService,
)

DEFAULT_ROLE_ID = 1
BOT_MEMBER_ID = 2


def _permissions(
    *,
    view_channel: bool,
    send_messages: bool,
) -> discord.Permissions:
    """Create deterministic effective Discord permissions."""

    permissions = discord.Permissions.none()

    permissions.update(
        view_channel=view_channel,
        send_messages=send_messages,
    )

    return permissions


def _configure_channel_permissions(
    channel: MagicMock,
    *,
    everyone_can_view: bool,
    bot_can_view: bool,
    bot_can_send: bool,
) -> None:
    """Configure effective permissions and editable overwrites."""

    def permissions_for(
        target,
    ):
        if target.id == DEFAULT_ROLE_ID:
            return _permissions(
                view_channel=everyone_can_view,
                send_messages=False,
            )

        if target.id == BOT_MEMBER_ID:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=bot_can_send,
            )

        return discord.Permissions.none()

    channel.permissions_for.side_effect = permissions_for

    channel.overwrites_for.side_effect = lambda _target: discord.PermissionOverwrite()

    channel.set_permissions = AsyncMock()


def _text_channel(
    *,
    channel_id: int,
    name: str,
    everyone_can_view: bool = False,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> MagicMock:
    """Create one Discord text channel mock."""

    channel = MagicMock(
        spec=discord.TextChannel,
    )

    channel.id = channel_id
    channel.name = name

    _configure_channel_permissions(
        channel,
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
    )

    return channel


def _forum_channel(
    *,
    channel_id: int,
    name: str,
    everyone_can_view: bool = False,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> MagicMock:
    """Create one Discord forum channel mock."""

    channel = MagicMock(
        spec=discord.ForumChannel,
    )

    channel.id = channel_id
    channel.name = name

    _configure_channel_permissions(
        channel,
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
    )

    return channel


def _category(
    *,
    category_id: int = 100,
    children: list[MagicMock] | None = None,
    everyone_can_view: bool = False,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> MagicMock:
    """Create one Discord category mock."""

    category = MagicMock(
        spec=discord.CategoryChannel,
    )

    category.id = category_id
    category.name = "Claviger Admin"
    category.channels = children or []

    _configure_channel_permissions(
        category,
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
    )

    return category


def _guild(
    *,
    channels: list[MagicMock] | None = None,
    manage_channels: bool = True,
) -> MagicMock:
    """Create one Discord guild mock for provisioning."""

    guild = MagicMock(
        spec=discord.Guild,
    )

    guild.id = 123

    default_role = MagicMock(
        spec=discord.Role,
    )

    default_role.id = DEFAULT_ROLE_ID

    bot_member = MagicMock(
        spec=discord.Member,
    )

    bot_member.id = BOT_MEMBER_ID

    guild_permissions = discord.Permissions.none()

    guild_permissions.update(
        manage_channels=manage_channels,
    )

    bot_member.guild_permissions = guild_permissions

    guild.default_role = default_role
    guild.me = bot_member
    guild.channels = channels or []

    guild.create_category = AsyncMock()
    guild.create_text_channel = AsyncMock()
    guild.create_forum = AsyncMock()

    return guild


def _candidate(
    *,
    category_id: int = 100,
) -> AdminCategoryCandidate:
    """Create one reconciliation category identity."""

    return AdminCategoryCandidate(
        category_id=category_id,
        category_name="Claviger Admin",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(),
    )


def _reconciliation(
    decision: AdminConfigurationReconciliationDecision,
    *,
    category_id: int | None = None,
) -> AdminConfigurationReconciliationResult:
    """Create one deterministic reconciliation result."""

    return AdminConfigurationReconciliationResult(
        decision=decision,
        category=(
            _candidate(
                category_id=category_id,
            )
            if category_id is not None
            else None
        ),
    )


def _configuration(
    *,
    command_channel_id: int | None = 200,
    activity_forum_id: int = 201,
    error_forum_id: int | None = 202,
) -> GuildAdminConfiguration:
    """Create one persisted administrative configuration."""

    return GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=command_channel_id,
        activity_forum_id=activity_forum_id,
        error_forum_id=error_forum_id,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "decision",
    [
        AdminConfigurationReconciliationDecision.KEEP,
        AdminConfigurationReconciliationDecision.IMPORT,
        AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
    ],
)
async def test_non_provisioning_decisions_do_not_mutate_discord(
    decision: AdminConfigurationReconciliationDecision,
) -> None:
    """Keep, import and choice states structural no-ops."""

    guild = _guild()

    configuration = (
        _configuration()
        if decision == AdminConfigurationReconciliationDecision.KEEP
        else None
    )

    category_id = (
        None
        if decision == AdminConfigurationReconciliationDecision.NEEDS_CHOICE
        else 100
    )

    result = await AdminStructureProvisioningService().provision(
        guild=guild,
        reconciliation=_reconciliation(
            decision,
            category_id=category_id,
        ),
        configuration=configuration,
    )

    assert result.changed is False

    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    guild.create_forum.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_builds_private_default_admin_structure() -> None:
    """Create deterministic ADMIN routing when Discord has no candidate."""

    guild = _guild()

    category = _category(
        category_id=100,
    )

    commands = _text_channel(
        channel_id=200,
        name="commands",
    )

    activity = _forum_channel(
        channel_id=201,
        name="activity",
    )

    errors = _forum_channel(
        channel_id=202,
        name="errors",
    )

    guild.create_category.return_value = category
    guild.create_text_channel.return_value = commands
    guild.create_forum.side_effect = [
        activity,
        errors,
    ]

    result = await AdminStructureProvisioningService().provision(
        guild=guild,
        reconciliation=_reconciliation(
            AdminConfigurationReconciliationDecision.CREATE,
        ),
        configuration=None,
    )

    assert result.changed is True
    assert result.created_category is True
    assert result.category_id == 100

    assert result.created_channel_ids == (
        200,
        201,
        202,
    )

    assert result.configuration == _configuration()

    guild.create_category.assert_awaited_once()
    guild.create_text_channel.assert_awaited_once()

    assert guild.create_forum.await_count == 2

    overwrites = guild.create_category.await_args.kwargs["overwrites"]

    assert overwrites[guild.default_role].view_channel is False

    assert overwrites[guild.me].view_channel is True

    assert overwrites[guild.me].send_messages is True


@pytest.mark.asyncio
async def test_create_requires_manage_channels_permission() -> None:
    """Fail before mutation when Claviger cannot manage Discord channels."""

    guild = _guild(
        manage_channels=False,
    )

    with pytest.raises(
        AdminStructureProvisioningPermissionError,
        match="Manage Channels",
    ):
        await AdminStructureProvisioningService().provision(
            guild=guild,
            reconciliation=_reconciliation(
                AdminConfigurationReconciliationDecision.CREATE,
            ),
            configuration=None,
        )

    guild.create_category.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_unconfigured_category_only_fills_missing_shape() -> None:
    """Add missing channel types without assigning existing forums business meaning."""

    existing_forum = _forum_channel(
        channel_id=201,
        name="legacy-reports",
    )

    category = _category(
        children=[
            existing_forum,
        ],
    )

    guild = _guild(
        channels=[
            category,
        ],
    )

    new_commands = _text_channel(
        channel_id=200,
        name="commands",
    )

    new_reporting = _forum_channel(
        channel_id=202,
        name="reporting",
    )

    guild.create_text_channel.return_value = new_commands

    guild.create_forum.return_value = new_reporting

    result = await AdminStructureProvisioningService().provision(
        guild=guild,
        reconciliation=_reconciliation(
            AdminConfigurationReconciliationDecision.COMPLETE,
            category_id=100,
        ),
        configuration=None,
    )

    assert result.changed is True
    assert result.created_category is False

    assert result.created_channel_ids == (
        200,
        202,
    )

    assert result.configuration is None

    assert guild.create_forum.await_args.args[0] == "reporting"

    guild.create_category.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_configured_category_recreates_missing_error_forum() -> None:
    """Replace only one missing persisted destination and preserve valid IDs."""

    commands = _text_channel(
        channel_id=200,
        name="commands",
    )

    activity = _forum_channel(
        channel_id=201,
        name="activity",
    )

    category = _category(
        children=[
            commands,
            activity,
        ],
    )

    guild = _guild(
        channels=[
            category,
        ],
    )

    new_errors = _forum_channel(
        channel_id=203,
        name="errors",
    )

    guild.create_forum.return_value = new_errors

    result = await AdminStructureProvisioningService().provision(
        guild=guild,
        reconciliation=_reconciliation(
            AdminConfigurationReconciliationDecision.COMPLETE,
            category_id=100,
        ),
        configuration=_configuration(),
    )

    assert result.created_channel_ids == (203,)

    assert result.configuration == GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=203,
    )

    guild.create_text_channel.assert_not_awaited()
    guild.create_forum.assert_awaited_once()


@pytest.mark.asyncio
async def test_complete_repairs_public_category_without_recreating_channels() -> None:
    """Repair category privacy while preserving valid configured destinations."""

    commands = _text_channel(
        channel_id=200,
        name="commands",
    )

    activity = _forum_channel(
        channel_id=201,
        name="activity",
    )

    errors = _forum_channel(
        channel_id=202,
        name="errors",
    )

    category = _category(
        children=[
            commands,
            activity,
            errors,
        ],
        everyone_can_view=True,
    )

    guild = _guild(
        channels=[
            category,
        ],
    )

    result = await AdminStructureProvisioningService().provision(
        guild=guild,
        reconciliation=_reconciliation(
            AdminConfigurationReconciliationDecision.COMPLETE,
            category_id=100,
        ),
        configuration=_configuration(),
    )

    assert result.changed is True
    assert result.category_permissions_repaired is True

    assert result.created_channel_ids == ()

    assert result.configuration == _configuration()

    category.set_permissions.assert_awaited_once()

    guild.create_text_channel.assert_not_awaited()
    guild.create_forum.assert_not_awaited()
