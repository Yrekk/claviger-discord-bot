import discord

from claviger.models.noctis_role_execution_result_model import (
    NoctisRoleExecutionResult,
)
from claviger.models.noctis_role_plan_model import NoctisRolePlan
from claviger.services.role_manager_service import RoleManager


class NoctisRoleExecutionError(RuntimeError):
    """Base error raised while applying a Noctis role plan."""


class NoctisRoleNotFoundError(NoctisRoleExecutionError):
    """Raised when a planned Discord role no longer exists."""


class NoctisRoleNotManageableError(NoctisRoleExecutionError):
    """Raised when Claviger cannot manage a planned Discord role."""


class NoctisRoleExecutorService:
    """Apply a validated Noctis role plan to a Discord member."""

    def __init__(
        self,
        role_manager: RoleManager,
    ) -> None:
        self.role_manager = role_manager

    async def execute(
        self,
        member: discord.Member,
        plan: NoctisRolePlan,
        *,
        reason: str | None = None,
    ) -> NoctisRoleExecutionResult:
        """Validate and apply all planned role changes."""

        if not plan.has_changes:
            return NoctisRoleExecutionResult(
                added_role_ids=(),
                removed_role_ids=(),
            )

        guild = member.guild
        bot_member = guild.me

        if bot_member is None:
            raise NoctisRoleExecutionError(
                "Claviger could not resolve its guild member."
            )

        planned_role_ids = tuple(
            dict.fromkeys(plan.remove_role_ids + plan.add_role_ids)
        )

        roles_by_id: dict[int, discord.Role] = {}

        for role_id in planned_role_ids:
            role = guild.get_role(
                role_id,
            )

            if role is None:
                raise NoctisRoleNotFoundError(
                    f"Discord role {role_id} no longer exists."
                )

            if role.managed or role.position >= bot_member.top_role.position:
                raise NoctisRoleNotManageableError(
                    (f"Discord role {role.name!r} cannot be managed by Claviger.")
                )

            roles_by_id[role_id] = role

        added_role_ids: list[int] = []
        removed_role_ids: list[int] = []

        # Remove obsolete accesses first so a failed update does not
        # preserve permissions the member explicitly deselected.
        for role_id in plan.remove_role_ids:
            changed = await self.role_manager.remove_role(
                member,
                roles_by_id[role_id],
                reason=reason,
            )

            if changed:
                removed_role_ids.append(
                    role_id,
                )

        for role_id in plan.add_role_ids:
            changed = await self.role_manager.add_role(
                member,
                roles_by_id[role_id],
                reason=reason,
            )

            if changed:
                added_role_ids.append(
                    role_id,
                )

        return NoctisRoleExecutionResult(
            added_role_ids=tuple(added_role_ids),
            removed_role_ids=tuple(removed_role_ids),
        )
