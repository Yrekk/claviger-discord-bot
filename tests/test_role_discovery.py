from unittest.mock import AsyncMock, MagicMock, Mock

import discord
import pytest

from claviger.services.role_discovery import RoleDiscoveryService


def create_role(
    *,
    role_id: int,
    name: str,
    position: int,
    managed: bool = False,
    default: bool = False,
) -> MagicMock:
    """Create a mocked Discord role with Discord-like hierarchy comparison."""
    role = MagicMock(spec=discord.Role)

    role.id = role_id
    role.name = name
    role.position = position
    role.managed = managed
    role.is_default.return_value = default

    def hierarchy_key(other: discord.Role) -> tuple[int, int]:
        return other.position, -other.id

    role.__lt__.side_effect = (
        lambda other: hierarchy_key(role) < hierarchy_key(other)
    )
    role.__gt__.side_effect = (
        lambda other: hierarchy_key(role) > hierarchy_key(other)
    )

    return role


def create_guild(
    *,
    roles: list[discord.Role],
    bot_role: discord.Role,
) -> Mock:
    """Create a mocked Discord guild containing Claviger."""
    guild = Mock(spec=discord.Guild)

    bot_member = Mock(spec=discord.Member)
    bot_member.top_role = bot_role

    guild.me = bot_member
    guild.fetch_roles = AsyncMock(return_value=roles)

    return guild


@pytest.mark.asyncio
async def test_get_hierarchy_splits_roles_around_claviger() -> None:
    """Split trusted and manageable roles around Claviger's role."""
    service = RoleDiscoveryService()

    dux = create_role(
        role_id=1,
        name="Dux Inutilis",
        position=100,
    )
    frater = create_role(
        role_id=2,
        name="Frater Sapientissimus",
        position=90,
    )
    claviger = create_role(
        role_id=3,
        name="Claviger",
        position=50,
    )
    member = create_role(
        role_id=4,
        name="Membre",
        position=40,
    )
    adult = create_role(
        role_id=5,
        name="Civis Noctis · 18+",
        position=30,
    )

    guild = create_guild(
        roles=[
            member,
            dux,
            adult,
            claviger,
            frater,
        ],
        bot_role=claviger,
    )

    hierarchy = await service.get_hierarchy(guild)

    assert hierarchy.bot_role is claviger
    assert hierarchy.trusted_roles == [
        dux,
        frater,
    ]
    assert hierarchy.manageable_roles == [
        member,
        adult,
    ]

    guild.fetch_roles.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_get_hierarchy_ignores_default_and_managed_roles() -> None:
    """Ignore @everyone and roles managed automatically by Discord."""
    service = RoleDiscoveryService()

    trusted = create_role(
        role_id=1,
        name="Imperatrix Augusta",
        position=100,
    )
    managed_above = create_role(
        role_id=2,
        name="Integration Role",
        position=90,
        managed=True,
    )
    claviger = create_role(
        role_id=3,
        name="Claviger",
        position=50,
    )
    managed_below = create_role(
        role_id=4,
        name="Bot Role",
        position=40,
        managed=True,
    )
    member = create_role(
        role_id=5,
        name="Membre",
        position=30,
    )
    everyone = create_role(
        role_id=6,
        name="@everyone",
        position=0,
        default=True,
    )

    guild = create_guild(
        roles=[
            everyone,
            managed_below,
            member,
            claviger,
            managed_above,
            trusted,
        ],
        bot_role=claviger,
    )

    hierarchy = await service.get_hierarchy(guild)

    assert hierarchy.trusted_roles == [
        trusted,
    ]
    assert hierarchy.manageable_roles == [
        member,
    ]


@pytest.mark.asyncio
async def test_get_hierarchy_raises_when_bot_member_is_missing() -> None:
    """Fail explicitly when Claviger cannot find itself in the guild."""
    service = RoleDiscoveryService()

    guild = Mock(spec=discord.Guild)
    guild.me = None

    with pytest.raises(
        RuntimeError,
        match="Claviger could not find its own member",
    ):
        await service.get_hierarchy(guild)


@pytest.mark.asyncio
async def test_get_hierarchy_raises_when_bot_role_is_missing() -> None:
    """Fail explicitly when Claviger's role is absent from fetched roles."""
    service = RoleDiscoveryService()

    claviger = create_role(
        role_id=3,
        name="Claviger",
        position=50,
    )
    member = create_role(
        role_id=4,
        name="Membre",
        position=40,
    )

    guild = create_guild(
        roles=[
            member,
        ],
        bot_role=claviger,
    )

    with pytest.raises(
        RuntimeError,
        match="Claviger's highest role could not be found",
    ):
        await service.get_hierarchy(guild)


@pytest.mark.asyncio
async def test_get_hierarchy_handles_roles_with_same_position() -> None:
    """Use Discord role ordering when multiple roles share a position."""
    service = RoleDiscoveryService()

    higher_role = create_role(
        role_id=10,
        name="Higher role",
        position=60,
    )
    lower_role = create_role(
        role_id=30,
        name="Lower role",
        position=60,
    )
    claviger = create_role(
        role_id=20,
        name="Claviger",
        position=60,
    )

    guild = create_guild(
        roles=[
            lower_role,
            claviger,
            higher_role,
        ],
        bot_role=claviger,
    )

    hierarchy = await service.get_hierarchy(guild)

    assert hierarchy.trusted_roles == [
        higher_role,
    ]
    assert hierarchy.manageable_roles == [
        lower_role,
    ]