from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.member_role_plan_model import MemberRolePlan
from claviger.services.member_role_executor_service import (
    MemberRoleExecutionError,
    MemberRoleExecutorService,
    MemberRoleNotFoundError,
    MemberRoleNotManageableError,
)
from claviger.services.role_manager_service import RoleManager


def create_role(
    *,
    role_id: int,
    name: str,
    position: int,
    managed: bool = False,
) -> Mock:
    """Create a Discord role for member executor tests."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name
    role.position = position
    role.managed = managed

    return role


def create_member(
    *,
    roles_by_id: dict[int, discord.Role] | None = None,
    bot_position: int = 100,
) -> Mock:
    """Create a Discord member and guild for executor tests."""

    member = Mock(
        spec=discord.Member,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    bot_top_role = Mock(
        spec=discord.Role,
    )

    bot_top_role.position = bot_position
    bot_member.top_role = bot_top_role

    guild.me = bot_member

    available_roles = roles_by_id or {}

    guild.get_role = Mock(
        side_effect=lambda role_id: available_roles.get(
            role_id,
        )
    )

    member.guild = guild

    return member


def create_executor() -> tuple[
    MemberRoleExecutorService,
    Mock,
]:
    """Create the executor with a mocked role manager."""

    role_manager = Mock(
        spec=RoleManager,
    )

    role_manager.add_role = AsyncMock(
        return_value=True,
    )

    role_manager.remove_role = AsyncMock(
        return_value=True,
    )

    return (
        MemberRoleExecutorService(
            role_manager,
        ),
        role_manager,
    )


@pytest.mark.asyncio
async def test_member_executor_returns_empty_result_for_empty_plan() -> None:
    """Do not touch Discord when the plan contains no changes."""

    executor, role_manager = create_executor()

    member = Mock(
        spec=discord.Member,
    )

    result = await executor.execute(
        member,
        MemberRolePlan(),
        reason="Member questionnaire update",
    )

    assert result.added_role_ids == ()
    assert result.removed_role_ids == ()
    assert result.change_count == 0
    assert result.has_changes is False

    role_manager.add_role.assert_not_awaited()
    role_manager.remove_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_executor_removes_before_adding_roles() -> None:
    """Apply removals before additions and report actual mutations."""

    removed_interest = create_role(
        role_id=10,
        name="interest-musicae",
        position=20,
    )

    member_role = create_role(
        role_id=100,
        name="Membre",
        position=30,
    )

    member = create_member(
        roles_by_id={
            10: removed_interest,
            100: member_role,
        }
    )

    executor, role_manager = create_executor()

    operations: list[str] = []

    async def remove_role(
        member_argument: discord.Member,
        role: discord.Role,
        *,
        reason: str | None = None,
    ) -> bool:
        operations.append(
            f"remove:{role.id}",
        )
        return True

    async def add_role(
        member_argument: discord.Member,
        role: discord.Role,
        *,
        reason: str | None = None,
    ) -> bool:
        operations.append(
            f"add:{role.id}",
        )
        return True

    role_manager.remove_role.side_effect = remove_role
    role_manager.add_role.side_effect = add_role

    result = await executor.execute(
        member,
        MemberRolePlan(
            add_role_ids=(100,),
            remove_role_ids=(10,),
        ),
        reason="Member questionnaire update",
    )

    assert operations == [
        "remove:10",
        "add:100",
    ]

    assert result.removed_role_ids == (10,)

    assert result.added_role_ids == (100,)

    assert result.change_count == 2
    assert result.has_changes is True


@pytest.mark.asyncio
async def test_member_executor_preflights_all_roles_before_mutation() -> None:
    """Reject a missing role before applying any earlier valid mutation."""

    removable_role = create_role(
        role_id=10,
        name="interest-musicae",
        position=20,
    )

    member = create_member(
        roles_by_id={
            10: removable_role,
        }
    )

    executor, role_manager = create_executor()

    with pytest.raises(
        MemberRoleNotFoundError,
        match="100",
    ):
        await executor.execute(
            member,
            MemberRolePlan(
                add_role_ids=(100,),
                remove_role_ids=(10,),
            ),
        )

    role_manager.remove_role.assert_not_awaited()
    role_manager.add_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_executor_rejects_managed_role() -> None:
    """Reject Discord-managed roles during preflight."""

    managed_role = create_role(
        role_id=100,
        name="Managed role",
        position=20,
        managed=True,
    )

    member = create_member(
        roles_by_id={
            100: managed_role,
        }
    )

    executor, role_manager = create_executor()

    with pytest.raises(
        MemberRoleNotManageableError,
        match="Managed role",
    ):
        await executor.execute(
            member,
            MemberRolePlan(
                add_role_ids=(100,),
            ),
        )

    role_manager.add_role.assert_not_awaited()
    role_manager.remove_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_executor_rejects_role_above_claviger() -> None:
    """Reject roles at or above Claviger's highest role."""

    protected_role = create_role(
        role_id=100,
        name="Protected role",
        position=100,
    )

    member = create_member(
        roles_by_id={
            100: protected_role,
        },
        bot_position=100,
    )

    executor, role_manager = create_executor()

    with pytest.raises(
        MemberRoleNotManageableError,
        match="Protected role",
    ):
        await executor.execute(
            member,
            MemberRolePlan(
                add_role_ids=(100,),
            ),
        )

    role_manager.add_role.assert_not_awaited()
    role_manager.remove_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_executor_requires_claviger_guild_member() -> None:
    """Reject execution when Claviger's guild member cannot be resolved."""

    role = create_role(
        role_id=100,
        name="Membre",
        position=20,
    )

    member = create_member(
        roles_by_id={
            100: role,
        }
    )

    member.guild.me = None

    executor, role_manager = create_executor()

    with pytest.raises(
        MemberRoleExecutionError,
        match="could not resolve",
    ):
        await executor.execute(
            member,
            MemberRolePlan(
                add_role_ids=(100,),
            ),
        )

    role_manager.add_role.assert_not_awaited()
    role_manager.remove_role.assert_not_awaited()
