from unittest.mock import AsyncMock, Mock, call

import discord
import pytest

from claviger.models.noctis_role_plan_model import NoctisRolePlan
from claviger.services.noctis_role_executor_service import (
    NoctisRoleExecutorService,
    NoctisRoleNotFoundError,
    NoctisRoleNotManageableError,
)
from claviger.services.role_manager_service import RoleManager


def create_role(
    *,
    role_id: int,
    name: str,
    position: int = 10,
    managed: bool = False,
) -> Mock:
    """Create a mocked Discord role."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name
    role.position = position
    role.managed = managed

    return role


def create_member(
    roles: dict[int, Mock],
    *,
    bot_position: int = 100,
) -> Mock:
    """Create a guild member with role lookup support."""

    member = Mock(
        spec=discord.Member,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    top_role = Mock(
        spec=discord.Role,
    )
    top_role.position = bot_position

    bot_member.top_role = top_role
    guild.me = bot_member

    guild.get_role.side_effect = roles.get

    member.guild = guild

    return member


@pytest.mark.asyncio
async def test_execute_applies_removals_then_additions() -> None:
    """Apply a valid plan through the shared RoleManager."""

    roles = {
        1: create_role(
            role_id=1,
            name="Civis Noctis - 18+",
        ),
        10: create_role(
            role_id=10,
            name="access-no-ia-yuri",
        ),
        11: create_role(
            role_id=11,
            name="access-ia-yuri",
        ),
        20: create_role(
            role_id=20,
            name="access-no-ia-bdsm",
        ),
    }

    member = create_member(
        roles,
    )

    role_manager = Mock(
        spec=RoleManager,
    )
    role_manager.remove_role = AsyncMock(
        return_value=True,
    )
    role_manager.add_role = AsyncMock(
        return_value=True,
    )

    service = NoctisRoleExecutorService(
        role_manager=role_manager,
    )

    result = await service.execute(
        member,
        NoctisRolePlan(
            add_role_ids=(1, 20),
            remove_role_ids=(10, 11),
        ),
        reason="Noctis questionnaire update",
    )

    role_manager.remove_role.assert_has_awaits(
        [
            call(
                member,
                roles[10],
                reason="Noctis questionnaire update",
            ),
            call(
                member,
                roles[11],
                reason="Noctis questionnaire update",
            ),
        ]
    )

    role_manager.add_role.assert_has_awaits(
        [
            call(
                member,
                roles[1],
                reason="Noctis questionnaire update",
            ),
            call(
                member,
                roles[20],
                reason="Noctis questionnaire update",
            ),
        ]
    )

    assert result.removed_role_ids == (
        10,
        11,
    )

    assert result.added_role_ids == (
        1,
        20,
    )

    assert result.change_count == 4


@pytest.mark.asyncio
async def test_execute_skips_discord_when_plan_is_empty() -> None:
    """Do nothing when the member already matches the desired state."""

    role_manager = Mock(
        spec=RoleManager,
    )
    role_manager.remove_role = AsyncMock()
    role_manager.add_role = AsyncMock()

    service = NoctisRoleExecutorService(
        role_manager=role_manager,
    )

    member = Mock(
        spec=discord.Member,
    )

    result = await service.execute(
        member,
        NoctisRolePlan(
            add_role_ids=(),
            remove_role_ids=(),
        ),
    )

    role_manager.remove_role.assert_not_awaited()
    role_manager.add_role.assert_not_awaited()

    assert result.change_count == 0


@pytest.mark.asyncio
async def test_execute_rejects_missing_role_before_any_change() -> None:
    """Abort before mutation when any planned role is missing."""

    roles = {
        10: create_role(
            role_id=10,
            name="access-no-ia-yuri",
        ),
    }

    member = create_member(
        roles,
    )

    role_manager = Mock(
        spec=RoleManager,
    )
    role_manager.remove_role = AsyncMock()
    role_manager.add_role = AsyncMock()

    service = NoctisRoleExecutorService(
        role_manager=role_manager,
    )

    with pytest.raises(
        NoctisRoleNotFoundError,
        match="999",
    ):
        await service.execute(
            member,
            NoctisRolePlan(
                add_role_ids=(999,),
                remove_role_ids=(10,),
            ),
        )

    role_manager.remove_role.assert_not_awaited()
    role_manager.add_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_rejects_unmanageable_role_before_any_change() -> None:
    """Abort before mutation when Claviger cannot manage a role."""

    roles = {
        10: create_role(
            role_id=10,
            name="access-no-ia-yuri",
        ),
        20: create_role(
            role_id=20,
            name="Too High",
            position=100,
        ),
    }

    member = create_member(
        roles,
        bot_position=100,
    )

    role_manager = Mock(
        spec=RoleManager,
    )
    role_manager.remove_role = AsyncMock()
    role_manager.add_role = AsyncMock()

    service = NoctisRoleExecutorService(
        role_manager=role_manager,
    )

    with pytest.raises(
        NoctisRoleNotManageableError,
        match="Too High",
    ):
        await service.execute(
            member,
            NoctisRolePlan(
                add_role_ids=(20,),
                remove_role_ids=(10,),
            ),
        )

    role_manager.remove_role.assert_not_awaited()
    role_manager.add_role.assert_not_awaited()
