from unittest.mock import MagicMock

import discord
import pytest

from claviger.services.admin_structure_discovery_service import (
    AdminStructureDiscoveryService,
)

DEFAULT_ROLE_ID = 1
BOT_MEMBER_ID = 2


def _permissions(
    *,
    view_channel: bool,
    send_messages: bool = False,
    create_public_threads: bool = False,
) -> discord.Permissions:
    """Create deterministic effective Discord permissions."""

    permissions = discord.Permissions.none()

    permissions.update(
        view_channel=view_channel,
        send_messages=send_messages,
        create_public_threads=create_public_threads,
    )

    return permissions


def _permission_resolver(
    *,
    everyone_can_view: bool,
    bot_can_view: bool,
    bot_can_send: bool,
    bot_can_create_public_threads: bool = False,
):
    """Build a permissions_for side effect for Discord channel mocks."""

    def permissions_for(
        target: discord.Role | discord.Member,
    ) -> discord.Permissions:
        if target.id == DEFAULT_ROLE_ID:
            return _permissions(
                view_channel=everyone_can_view,
            )

        if target.id == BOT_MEMBER_ID:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=bot_can_send,
                create_public_threads=bot_can_create_public_threads,
            )

        return discord.Permissions.none()

    return permissions_for


def _create_text_channel(
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

    channel.permissions_for.side_effect = _permission_resolver(
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
    )

    return channel


def _create_forum_channel(
    *,
    channel_id: int,
    name: str,
    everyone_can_view: bool = False,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
    bot_can_create_public_threads: bool = False,
) -> MagicMock:
    """Create one Discord forum channel mock."""

    channel = MagicMock(
        spec=discord.ForumChannel,
    )

    channel.id = channel_id
    channel.name = name

    channel.permissions_for.side_effect = _permission_resolver(
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
        bot_can_create_public_threads=bot_can_create_public_threads,
    )

    return channel


def _create_voice_channel(
    *,
    channel_id: int,
    name: str,
    everyone_can_view: bool = False,
) -> MagicMock:
    """Create one unsupported child channel for privacy validation."""

    channel = MagicMock(
        spec=discord.VoiceChannel,
    )

    channel.id = channel_id
    channel.name = name

    channel.permissions_for.side_effect = _permission_resolver(
        everyone_can_view=everyone_can_view,
        bot_can_view=True,
        bot_can_send=False,
    )

    return channel


def _create_category(
    *,
    category_id: int,
    name: str,
    children: list[MagicMock],
    everyone_can_view: bool = False,
    bot_can_view: bool = True,
) -> MagicMock:
    """Create one Discord category mock."""

    category = MagicMock(
        spec=discord.CategoryChannel,
    )

    category.id = category_id
    category.name = name
    category.channels = children

    category.permissions_for.side_effect = _permission_resolver(
        everyone_can_view=everyone_can_view,
        bot_can_view=bot_can_view,
        bot_can_send=False,
    )

    return category


def _create_guild(
    *,
    channels: list[MagicMock],
) -> MagicMock:
    """Create one Discord guild mock for admin discovery."""

    guild = MagicMock(
        spec=discord.Guild,
    )

    default_role = MagicMock(
        spec=discord.Role,
    )
    default_role.id = DEFAULT_ROLE_ID

    bot_member = MagicMock(
        spec=discord.Member,
    )
    bot_member.id = BOT_MEMBER_ID

    guild.default_role = default_role
    guild.me = bot_member
    guild.channels = channels

    return guild


def test_discover_returns_no_candidate_without_admin_category() -> None:
    """Ignore categories whose names do not identify administration."""

    category = _create_category(
        category_id=100,
        name="community",
        children=[],
    )

    guild = _create_guild(
        channels=[category],
    )

    result = AdminStructureDiscoveryService().discover(
        guild,
    )

    assert result.categories == ()
    assert result.has_candidates is False
    assert result.is_ambiguous is False
    assert result.single_candidate is None


def test_discover_matches_admin_category_case_insensitively() -> None:
    """Detect an administrative category without requiring an exact name."""

    category = _create_category(
        category_id=100,
        name="Administration",
        children=[],
    )

    guild = _create_guild(
        channels=[category],
    )

    result = AdminStructureDiscoveryService().discover(
        guild,
    )

    assert result.has_candidates is True
    assert result.single_candidate is not None
    assert result.single_candidate.category_id == 100
    assert result.single_candidate.category_name == "Administration"


def test_discover_collects_supported_admin_channels() -> None:
    """Collect text and forum channels without assigning business meaning."""

    commands = _create_text_channel(
        channel_id=200,
        name="commands",
    )

    activity = _create_forum_channel(
        channel_id=201,
        name="activity",
    )

    errors = _create_forum_channel(
        channel_id=202,
        name="errors",
    )

    category = _create_category(
        category_id=100,
        name="Claviger Admin",
        children=[
            commands,
            activity,
            errors,
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    result = AdminStructureDiscoveryService().discover(
        guild,
    )

    candidate = result.single_candidate

    assert candidate is not None

    assert {channel.channel_id for channel in candidate.text_channels} == {
        200,
    }

    assert {channel.channel_id for channel in candidate.forum_channels} == {
        201,
        202,
    }


def test_complete_private_admin_structure_is_ready() -> None:
    """Accept one private text channel and two private usable forums."""

    commands = _create_text_channel(
        channel_id=200,
        name="commands",
    )

    activity = _create_forum_channel(
        channel_id=201,
        name="activity",
    )

    errors = _create_forum_channel(
        channel_id=202,
        name="errors",
    )

    category = _create_category(
        category_id=100,
        name="admin",
        children=[
            commands,
            activity,
            errors,
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = AdminStructureDiscoveryService().discover(guild).single_candidate

    assert candidate is not None
    assert candidate.is_private is True
    assert candidate.has_required_shape is True
    assert candidate.has_required_usable_shape is True
    assert candidate.is_structurally_ready is True


def test_public_admin_category_is_not_ready() -> None:
    """Reject an administrative category visible to @everyone."""

    category = _create_category(
        category_id=100,
        name="admin",
        everyone_can_view=True,
        children=[
            _create_text_channel(
                channel_id=200,
                name="commands",
            ),
            _create_forum_channel(
                channel_id=201,
                name="activity",
            ),
            _create_forum_channel(
                channel_id=202,
                name="errors",
            ),
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = AdminStructureDiscoveryService().discover(guild).single_candidate

    assert candidate is not None
    assert candidate.is_private is False
    assert candidate.is_structurally_ready is False


def test_public_child_makes_admin_category_not_private() -> None:
    """Reject a category when any child explicitly exposes @everyone."""

    public_voice = _create_voice_channel(
        channel_id=203,
        name="public-voice",
        everyone_can_view=True,
    )

    category = _create_category(
        category_id=100,
        name="admin",
        children=[
            _create_text_channel(
                channel_id=200,
                name="commands",
            ),
            _create_forum_channel(
                channel_id=201,
                name="activity",
            ),
            _create_forum_channel(
                channel_id=202,
                name="errors",
            ),
            public_voice,
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = AdminStructureDiscoveryService().discover(guild).single_candidate

    assert candidate is not None
    assert candidate.has_public_child is True
    assert candidate.is_private is False
    assert candidate.is_structurally_ready is False


def test_incomplete_admin_structure_is_not_ready() -> None:
    """Require one text channel and at least two forums."""

    category = _create_category(
        category_id=100,
        name="admin",
        children=[
            _create_text_channel(
                channel_id=200,
                name="commands",
            ),
            _create_forum_channel(
                channel_id=201,
                name="activity",
            ),
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = AdminStructureDiscoveryService().discover(guild).single_candidate

    assert candidate is not None
    assert candidate.has_required_shape is False
    assert candidate.is_structurally_ready is False


def test_unusable_admin_channel_prevents_ready_state() -> None:
    """Reject a structure when Claviger cannot use enough report forums."""

    unusable_errors = _create_forum_channel(
        channel_id=202,
        name="errors",
        bot_can_send=False,
    )

    category = _create_category(
        category_id=100,
        name="admin",
        children=[
            _create_text_channel(
                channel_id=200,
                name="commands",
            ),
            _create_forum_channel(
                channel_id=201,
                name="activity",
            ),
            unusable_errors,
        ],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = AdminStructureDiscoveryService().discover(guild).single_candidate

    assert candidate is not None
    assert candidate.has_required_shape is True
    assert candidate.has_required_usable_shape is False
    assert candidate.is_structurally_ready is False


def test_multiple_admin_categories_are_ambiguous() -> None:
    """Require human choice when several admin categories exist."""

    first = _create_category(
        category_id=100,
        name="admin",
        children=[],
    )

    second = _create_category(
        category_id=101,
        name="staff-admin",
        children=[],
    )

    guild = _create_guild(
        channels=[
            first,
            second,
        ],
    )

    result = AdminStructureDiscoveryService().discover(
        guild,
    )

    assert len(result.categories) == 2
    assert result.has_candidates is True
    assert result.is_ambiguous is True
    assert result.single_candidate is None


def test_discover_requires_claviger_guild_member() -> None:
    """Fail safely when Discord cannot resolve Claviger in the guild."""

    guild = _create_guild(
        channels=[],
    )

    guild.me = None

    with pytest.raises(
        RuntimeError,
        match="Claviger member could not be resolved",
    ):
        AdminStructureDiscoveryService().discover(
            guild,
        )


def test_forum_is_usable_with_send_messages_without_create_public_threads() -> None:
    """Use Discord forum-post permissions rather than text-thread permissions."""

    forum = _create_forum_channel(
        channel_id=201,
        name="activity",
        bot_can_send=True,
        bot_can_create_public_threads=False,
    )

    category = _create_category(
        category_id=100,
        name="admin",
        children=[forum],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = (
        AdminStructureDiscoveryService()
        .discover(
            guild,
        )
        .single_candidate
    )

    assert candidate is not None
    assert len(candidate.forum_channels) == 1
    assert candidate.forum_channels[0].bot_usable is True


def test_create_public_threads_does_not_make_forum_usable_without_send_messages() -> (
    None
):
    """Reject forum posting when Discord's SEND_MESSAGES permission is absent."""

    forum = _create_forum_channel(
        channel_id=201,
        name="activity",
        bot_can_send=False,
        bot_can_create_public_threads=True,
    )

    category = _create_category(
        category_id=100,
        name="admin",
        children=[forum],
    )

    guild = _create_guild(
        channels=[category],
    )

    candidate = (
        AdminStructureDiscoveryService()
        .discover(
            guild,
        )
        .single_candidate
    )

    assert candidate is not None
    assert len(candidate.forum_channels) == 1
    assert candidate.forum_channels[0].bot_usable is False
