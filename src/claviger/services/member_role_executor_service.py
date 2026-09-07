import discord

from claviger.models.member_role_execution_result_model import (
    MemberRoleExecutionResult,
)
from claviger.models.member_role_plan_model import MemberRolePlan
from claviger.services.role_manager_service import RoleManager


class MemberRoleExecutionError(RuntimeError):
    """Base error raised while applying a member role plan."""


class MemberRoleNotFoundError(MemberRoleExecutionError):
    """Raised when a planned Discord role no longer exists."""


class MemberRoleNotManageableError(MemberRoleExecutionError):
    """Raised when Claviger cannot manage a planned Discord role."""


class MemberRoleExecutorService:
    """Apply a validated member role plan to a Discord member."""

    def __init__(
        self,
        role_manager: RoleManager,
    ) -> None:
        self.role_manager = role_manager

    async def execute(
        self,
        member: discord.Member,
        plan: MemberRolePlan,
        *,
        reason: str | None = None,
    ) -> MemberRoleExecutionResult:
        """Validate and apply all planned role changes."""

        if not plan.has_changes:
            return MemberRoleExecutionResult(
                added_role_ids=(),
                removed_role_ids=(),
            )

        guild = member.guild
        bot_member = guild.me

        if bot_member is None:
            raise MemberRoleExecutionError(
                "Claviger could not resolve its guild member."
            )

        planned_role_ids = tuple(
            dict.fromkeys(plan.remove_role_ids + plan.add_role_ids)
        )

        roles_by_id: dict[int, discord.Role] = {}

        # Resolve and validate every planned role before the first
        # Discord mutation. A bad plan must therefore fail atomically
        # at the preflight stage.
        for role_id in planned_role_ids:
            role = guild.get_role(
                role_id,
            )

            if role is None:
                raise MemberRoleNotFoundError(
                    f"Discord role {role_id} no longer exists."
                )

            if role.managed or role.position >= bot_member.top_role.position:
                raise MemberRoleNotManageableError(
                    (f"Discord role {role.name!r} cannot be managed by Claviger.")
                )

            roles_by_id[role_id] = role

        added_role_ids: list[int] = []
        removed_role_ids: list[int] = []

        # Remove deselected interests before adding new roles.
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

        return MemberRoleExecutionResult(
            added_role_ids=tuple(
                added_role_ids,
            ),
            removed_role_ids=tuple(
                removed_role_ids,
            ),
        )
