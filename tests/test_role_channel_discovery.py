from unittest.mock import MagicMock

import discord
import pytest

from claviger.services.role_channel_discovery import (
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


def create_channel(
    *,
    channel_id: int,
    name: str,
    visible_roles: set[int],
) -> MagicMock:
    """Create a text channel exposing explicit role visibility."""

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


def test_discover_returns_matching_role_with_unique_channel() -> None:
    """Discover one valid role-to-channel catalog mapping."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    channel = create_channel(
        channel_id=200,
        name="ia",
        visible_roles={100},
    )

    guild = create_guild(
        roles=[role],
        channels=[channel],
    )

    service = RoleChannelDiscoveryService()

    discoveries = service.discover(
        guild,
        prefix="interest-",
    )

    assert len(discoveries) == 1

    discovery = discoveries[0]

    assert discovery.role_id == 100
    assert discovery.role_name == "interest-ia"
    assert discovery.catalog_key == "ia"

    assert discovery.role_manageable is True

    assert discovery.channel_id == 200
    assert discovery.channel_name == "ia"

    assert discovery.channel_present is True
    assert discovery.mapping_valid is True


def test_discover_ignores_roles_outside_prefix() -> None:
    """Ignore Discord roles unrelated to the requested catalog."""

    role = create_role(
        role_id=100,
        name="access-ia-futa",
    )

    guild = create_guild(
        roles=[role],
        channels=[],
    )

    service = RoleChannelDiscoveryService()

    discoveries = service.discover(
        guild,
        prefix="interest-",
    )

    assert discoveries == []


def test_discover_ignores_empty_catalog_key() -> None:
    """Reject a role containing only the configured prefix."""

    role = create_role(
        role_id=100,
        name="interest-",
    )

    guild = create_guild(
        roles=[role],
        channels=[],
    )

    service = RoleChannelDiscoveryService()

    discoveries = service.discover(
        guild,
        prefix="interest-",
    )

    assert discoveries == []


def test_discover_marks_role_above_claviger_unmanageable() -> None:
    """Detect matching roles that Claviger cannot manage."""

    role = create_role(
        role_id=100,
        name="interest-ia",
        below_bot=False,
    )

    channel = create_channel(
        channel_id=200,
        name="ia",
        visible_roles={100},
    )

    guild = create_guild(
        roles=[role],
        channels=[channel],
    )

    service = RoleChannelDiscoveryService()

    discovery = service.discover(
        guild,
        prefix="interest-",
    )[0]

    assert discovery.role_manageable is False
    assert discovery.mapping_valid is True


def test_discover_marks_missing_channel_mapping_invalid() -> None:
    """Detect a matching role without an explicit content channel."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    guild = create_guild(
        roles=[role],
        channels=[],
    )

    service = RoleChannelDiscoveryService()

    discovery = service.discover(
        guild,
        prefix="interest-",
    )[0]

    assert discovery.channel_id is None
    assert discovery.channel_name is None
    assert discovery.channel_present is False
    assert discovery.mapping_valid is False


def test_discover_marks_multiple_channels_mapping_invalid() -> None:
    """Reject ambiguous mappings when a role exposes several channels."""

    role = create_role(
        role_id=100,
        name="interest-ia",
    )

    first_channel = create_channel(
        channel_id=200,
        name="ia-one",
        visible_roles={100},
    )

    second_channel = create_channel(
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

    service = RoleChannelDiscoveryService()

    discovery = service.discover(
        guild,
        prefix="interest-",
    )[0]

    assert discovery.channel_id is None
    assert discovery.channel_name is None
    assert discovery.channel_present is False
    assert discovery.mapping_valid is False


def test_discover_supports_access_prefix_without_special_logic() -> None:
    """Use the same discovery engine for adult access roles."""

    role = create_role(
        role_id=100,
        name="access-ia-futa",
    )

    channel = create_channel(
        channel_id=200,
        name="ia-futa",
        visible_roles={100},
    )

    guild = create_guild(
        roles=[role],
        channels=[channel],
    )

    service = RoleChannelDiscoveryService()

    discovery = service.discover(
        guild,
        prefix="access-",
    )[0]

    assert discovery.catalog_key == "ia-futa"
    assert discovery.mapping_valid is True


def test_discover_rejects_empty_prefix() -> None:
    """Prevent accidental discovery of every Discord role."""

    guild = create_guild(
        roles=[],
        channels=[],
    )

    service = RoleChannelDiscoveryService()

    with pytest.raises(
        ValueError,
    ):
        service.discover(
            guild,
            prefix="",
        )


def test_discover_requires_claviger_guild_member() -> None:
    """Fail safely when Discord cannot resolve the bot member."""

    guild = create_guild(
        roles=[],
        channels=[],
    )
    guild.me = None

    service = RoleChannelDiscoveryService()

    with pytest.raises(
        RuntimeError,
    ):
        service.discover(
            guild,
            prefix="interest-",
        )
