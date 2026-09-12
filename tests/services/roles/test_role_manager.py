from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.role_manager_service import RoleManager


@pytest.mark.asyncio
async def test_add_role_adds_missing_role() -> None:
    manager = RoleManager()

    member = Mock(spec=discord.Member)
    role = Mock(spec=discord.Role)

    member.roles = []
    member.add_roles = AsyncMock()

    changed = await manager.add_role(
        member,
        role,
        reason="RoleManager test",
    )

    assert changed is True
    member.add_roles.assert_awaited_once_with(
        role,
        reason="RoleManager test",
    )


@pytest.mark.asyncio
async def test_add_role_does_nothing_when_role_is_already_present() -> None:
    manager = RoleManager()

    member = Mock(spec=discord.Member)
    role = Mock(spec=discord.Role)

    member.roles = [role]
    member.add_roles = AsyncMock()

    changed = await manager.add_role(member, role)

    assert changed is False
    member.add_roles.assert_not_awaited()


@pytest.mark.asyncio
async def test_remove_role_removes_existing_role() -> None:
    manager = RoleManager()

    member = Mock(spec=discord.Member)
    role = Mock(spec=discord.Role)

    member.roles = [role]
    member.remove_roles = AsyncMock()

    changed = await manager.remove_role(
        member,
        role,
        reason="RoleManager test",
    )

    assert changed is True
    member.remove_roles.assert_awaited_once_with(
        role,
        reason="RoleManager test",
    )


@pytest.mark.asyncio
async def test_remove_role_does_nothing_when_role_is_missing() -> None:
    manager = RoleManager()

    member = Mock(spec=discord.Member)
    role = Mock(spec=discord.Role)

    member.roles = []
    member.remove_roles = AsyncMock()

    changed = await manager.remove_role(member, role)

    assert changed is False
    member.remove_roles.assert_not_awaited()
