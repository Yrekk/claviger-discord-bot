from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflows.workflow_role_plan_model import WorkflowRolePlan
from claviger.services.roles.role_manager_service import RoleManager
from claviger.services.workflows.workflow_role_executor_service import (
    WorkflowRoleExecutionPartialError,
    WorkflowRoleExecutorService,
    WorkflowRoleNotManageableError,
)

pytestmark = pytest.mark.asyncio


def _role(
    role_id: int,
    *,
    position: int,
    managed: bool = False,
) -> MagicMock:
    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.name = f"role-{role_id}"
    role.position = position
    role.managed = managed
    role.is_default.return_value = False
    role.__lt__.side_effect = lambda other: role.position < other.position
    return role


def _member(*role_ids: int) -> tuple[MagicMock, dict[int, MagicMock]]:
    guild = MagicMock(spec=discord.Guild)
    bot_member = MagicMock(spec=discord.Member)
    bot_member.top_role = _role(999, position=100)
    guild.me = bot_member

    roles = {
        role_id: _role(role_id, position=10 + index)
        for index, role_id in enumerate(role_ids)
    }
    guild.get_role.side_effect = roles.get

    member = MagicMock(spec=discord.Member)
    member.guild = guild
    member.roles = list(roles.values())
    return member, roles


async def test_executor_preflights_all_roles_before_first_mutation() -> None:
    """Reject an unsafe plan without applying any earlier valid role change."""

    member, roles = _member(
        10,
        20,
    )
    roles[20].managed = True

    role_manager = MagicMock(spec=RoleManager)
    role_manager.add_role = AsyncMock()
    role_manager.remove_role = AsyncMock()

    executor = WorkflowRoleExecutorService(
        role_manager,
    )

    with pytest.raises(
        WorkflowRoleNotManageableError,
    ):
        await executor.execute(
            member,
            WorkflowRolePlan(
                add_role_ids=(10, 20),
            ),
        )

    role_manager.add_role.assert_not_awaited()
    role_manager.remove_role.assert_not_awaited()


async def test_executor_reports_successful_removal_before_partial_failure() -> None:
    """Preserve removals already applied before a later Discord failure."""

    member, _ = _member(
        10,
        20,
    )

    role_manager = MagicMock(spec=RoleManager)
    role_manager.remove_role = AsyncMock(
        side_effect=(
            True,
            RuntimeError("Discord removal failed."),
        )
    )
    role_manager.add_role = AsyncMock()

    executor = WorkflowRoleExecutorService(
        role_manager,
    )

    with pytest.raises(
        WorkflowRoleExecutionPartialError,
    ) as exc_info:
        await executor.execute(
            member,
            WorkflowRolePlan(
                remove_role_ids=(10, 20),
            ),
        )

    error = exc_info.value

    assert error.removed_role_ids == (10,)
    assert error.added_role_ids == ()
    assert isinstance(error.__cause__, RuntimeError)

    role_manager.add_role.assert_not_awaited()


async def test_executor_reports_removal_and_addition_before_partial_failure() -> None:
    """Preserve every successful mutation before a later addition fails."""

    member, _ = _member(
        10,
        20,
        30,
    )

    role_manager = MagicMock(spec=RoleManager)
    role_manager.remove_role = AsyncMock(
        return_value=True,
    )
    role_manager.add_role = AsyncMock(
        side_effect=(
            True,
            RuntimeError("Discord addition failed."),
        )
    )

    executor = WorkflowRoleExecutorService(
        role_manager,
    )

    with pytest.raises(
        WorkflowRoleExecutionPartialError,
    ) as exc_info:
        await executor.execute(
            member,
            WorkflowRolePlan(
                remove_role_ids=(10,),
                add_role_ids=(20, 30),
            ),
        )

    error = exc_info.value

    assert error.removed_role_ids == (10,)
    assert error.added_role_ids == (20,)
    assert isinstance(error.__cause__, RuntimeError)


async def test_executor_keeps_first_mutation_failure_non_partial() -> None:
    """Do not claim partial mutation when Discord failed before any change."""

    member, _ = _member(
        10,
    )

    role_manager = MagicMock(spec=RoleManager)
    role_manager.remove_role = AsyncMock(
        side_effect=RuntimeError("Discord failed before changing anything."),
    )
    role_manager.add_role = AsyncMock()

    executor = WorkflowRoleExecutorService(
        role_manager,
    )

    with pytest.raises(
        RuntimeError,
        match="before changing anything",
    ):
        await executor.execute(
            member,
            WorkflowRolePlan(
                remove_role_ids=(10,),
            ),
        )
