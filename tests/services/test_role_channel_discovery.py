from unittest.mock import MagicMock

import discord
import pytest

from claviger.services.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)


def create_role(
    *,
    role_id: int,
    name: str,
    below_bot: bool = True,
) -> MagicMock:
    """Create a Discord role mock with deterministic hierarchy behavior."""

    role = MagicMock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name
    role.__lt__.return_value = below_bot

    return role


def create_text_channel(
    *,
    channel_id: int,
    name: str,
    visible_roles: set[int],
) -> MagicMock:
    """Create a text channel with explicit role visibility."""

    channel = MagicMock(
        spec=discord.TextChannel,
    )

    channel.id = channel_id
    channel.name = name

    def overwrites_for(
        role: discord.Role,
    ) -> discord.PermissionOverwrite:
        overwrite = discord.PermissionOverwrite()

        if role.id in visible_roles:
            overwrite.view_channel = True

        return overwrite

    channel.overwrites_for.side_effect = overwrites_for

    return channel


def create_forum_channel(
    *,
    channel_id: int,
    name: str,
    visible_roles: set[int],
) -> MagicMock:
    """Create a forum channel with explicit role visibility."""

    channel = MagicMock(
        spec=discord.ForumChannel,
    )

    channel.id = channel_id
    channel.name = name

    def overwrites_for(
        role: discord.Role,
    ) -> discord.PermissionOverwrite:
        overwrite = discord.PermissionOverwrite()

        if role.id in visible_roles:
            overwrite.view_channel = True

        return overwrite

    channel.overwrites_for.side_effect = overwrites_for

    return channel


def create_guild(
    *,
    roles: list[MagicMock],
    channels: list[MagicMock],
) -> MagicMock:
    """Create a Discord guild mock for discovery tests."""

    guild = MagicMock(
        spec=discord.Guild,
    )

    bot_member = MagicMock(
        spec=discord.Member,
    )

    bot_member.top_role = MagicMock(
        spec=discord.Role,
    )

    guild.me = bot_member
    guild.roles = roles
    guild.channels = channels

    return guild


def test_build_snapshot_contains_all_roles_and_content_channels() -> None:
    """Capture catalog and non-catalog Discord roles in one snapshot."""

    interest_role = create_role(
        role_id=100,
        name="interest-ia",
    )

    access_role = create_role(
        role_id=101,
        name="access-ia-futa",
    )

    ordinary_role = create_role(
        role_id=102,
        name="Membre",
    )

    text_channel = create_text_channel(
        channel_id=200,
        name="ia",
        visible_roles={100},
    )

    forum_channel = create_forum_channel(
        channel_id=201,
        name="ia-futa",
        visible_roles={101},
    )

    guild = create_guild(
        roles=[
            interest_role,
            access_role,
            ordinary_role,
        ],
        channels=[
            text_channel,
            forum_channel,
        ],
    )

    snapshot = RoleChannelDiscoveryService().build_snapshot(
        guild,
    )

    assert {role.role_id for role in snapshot.roles} == {
        100,
        101,
        102,
    }

    assert {channel.channel_id for channel in snapshot.channels} == {
        200,
        201,
    }


def test_build_snapshot_records_explicit_channel_mapping() -> None:
    """Record channels explicitly visible to each Discord role."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    channel = create_text_channel(
        channel_id=200,
        name="ia",
        visible_roles={100},
    )

    guild = create_guild(
        roles=[role],
        channels=[channel],
    )

    snapshot = RoleChannelDiscoveryService().build_snapshot(
        guild,
    )

    assert snapshot.roles[0].explicit_channel_ids == (200,)


def test_build_snapshot_records_multiple_explicit_channels() -> None:
    """Preserve ambiguous role mappings for later planner validation."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    first_channel = create_text_channel(
        channel_id=200,
        name="ia-one",
        visible_roles={100},
    )

    second_channel = create_forum_channel(
        channel_id=201,
        name="ia-two",
        visible_roles={100},
    )

    guild = create_guild(
        roles=[role],
        channels=[
            first_channel,
            second_channel,
        ],
    )

    snapshot = RoleChannelDiscoveryService().build_snapshot(
        guild,
    )

    assert snapshot.roles[0].explicit_channel_ids == (
        200,
        201,
    )


def test_build_snapshot_ignores_unsupported_channel_types() -> None:
    """Ignore voice channels when building role catalog mappings."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    voice_channel = MagicMock(
        spec=discord.VoiceChannel,
    )

    voice_channel.id = 300
    voice_channel.name = "voice"

    guild = create_guild(
        roles=[role],
        channels=[voice_channel],
    )

    snapshot = RoleChannelDiscoveryService().build_snapshot(
        guild,
    )

    assert snapshot.channels == ()
    assert snapshot.roles[0].explicit_channel_ids == ()


def test_build_snapshot_records_role_manageability() -> None:
    """Capture whether Claviger can manage each Discord role."""

    manageable_role = create_role(
        role_id=100,
        name="interest-ia",
        below_bot=True,
    )

    unmanageable_role = create_role(
        role_id=101,
        name="access-ia-futa",
        below_bot=False,
    )

    guild = create_guild(
        roles=[
            manageable_role,
            unmanageable_role,
        ],
        channels=[],
    )

    snapshot = RoleChannelDiscoveryService().build_snapshot(
        guild,
    )

    assert snapshot.roles[0].role_manageable is True
    assert snapshot.roles[1].role_manageable is False


def test_build_snapshot_requires_claviger_guild_member() -> None:
    """Fail safely when Discord cannot resolve Claviger in the guild."""

    guild = create_guild(
        roles=[],
        channels=[],
    )

    guild.me = None

    with pytest.raises(
        RuntimeError,
    ):
        RoleChannelDiscoveryService().build_snapshot(
            guild,
        )
