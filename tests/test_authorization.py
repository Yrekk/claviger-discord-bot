from unittest.mock import MagicMock, Mock

import discord
import pytest

from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)


def create_role(
    *,
    role_id: int,
    position: int,
    managed: bool = False,
    default: bool = False,
) -> MagicMock:
    """Create a mocked Discord role with Discord-like hierarchy comparison."""
    role = MagicMock(spec=discord.Role)

    role.id = role_id
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


def create_context(
    *,
    owner_id: int = 1,
    member_id: int = 2,
    member_roles: list[discord.Role],
    bot_role: discord.Role,
) -> tuple[Mock, Mock]:
    """Create mocked member and guild objects for authorization tests."""
    guild = Mock(spec=discord.Guild)
    guild.owner_id = owner_id

    bot_member = Mock(spec=discord.Member)
    bot_member.top_role = bot_role
    guild.me = bot_member

    member = Mock(spec=discord.Member)
    member.id = member_id
    member.roles = member_roles

    return member, guild


@pytest.mark.asyncio
async def test_owner_is_always_allowed() -> None:
    """Allow the guild owner regardless of the requested capability."""
    service = AuthorizationService()

    bot_role = create_role(
        role_id=20,
        position=50,
    )

    member, guild = create_context(
        owner_id=1,
        member_id=1,
        member_roles=[],
        bot_role=bot_role,
    )

    assert await service.is_allowed(
        member,
        guild,
        Capability.ROLE_SCAN,
    )


@pytest.mark.asyncio
async def test_trusted_member_can_use_say() -> None:
    """Allow say when the member has a trusted role above Claviger."""
    service = AuthorizationService()

    bot_role = create_role(
        role_id=20,
        position=50,
    )
    trusted_role = create_role(
        role_id=10,
        position=60,
    )

    member, guild = create_context(
        member_roles=[
            trusted_role,
        ],
        bot_role=bot_role,
    )

    assert await service.is_allowed(
        member,
        guild,
        Capability.SAY,
    )


@pytest.mark.asyncio
async def test_trusted_member_cannot_use_role_scan() -> None:
    """Do not grant sensitive capabilities to trusted roles by default."""
    service = AuthorizationService()

    bot_role = create_role(
        role_id=20,
        position=50,
    )
    trusted_role = create_role(
        role_id=10,
        position=60,
    )

    member, guild = create_context(
        member_roles=[
            trusted_role,
        ],
        bot_role=bot_role,
    )

    assert not await service.is_allowed(
        member,
        guild,
        Capability.ROLE_SCAN,
    )


@pytest.mark.asyncio
async def test_member_below_claviger_cannot_use_say() -> None:
    """Reject say when all member roles are below Claviger."""
    service = AuthorizationService()

    bot_role = create_role(
        role_id=20,
        position=50,
    )
    member_role = create_role(
        role_id=30,
        position=40,
    )

    member, guild = create_context(
        member_roles=[
            member_role,
        ],
        bot_role=bot_role,
    )

    assert not await service.is_allowed(
        member,
        guild,
        Capability.SAY,
    )


@pytest.mark.asyncio
async def test_managed_role_above_claviger_does_not_grant_say() -> None:
    """Do not trust Discord-managed roles even when they are above Claviger."""
    service = AuthorizationService()

    bot_role = create_role(
        role_id=20,
        position=50,
    )
    managed_role = create_role(
        role_id=10,
        position=60,
        managed=True,
    )

    member, guild = create_context(
        member_roles=[
            managed_role,
        ],
        bot_role=bot_role,
    )

    assert not await service.is_allowed(
        member,
        guild,
        Capability.SAY,
    )