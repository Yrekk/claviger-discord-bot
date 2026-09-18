from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflows.workflow_role_plan_model import WorkflowRolePlan
from claviger.services.roles.role_manager_service import RoleManager
from claviger.services.workflows.workflow_role_executor_service import (
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
