import discord

from claviger.models.workflows.workflow_role_execution_result_model import (
    WorkflowRoleExecutionResult,
)
from claviger.models.workflows.workflow_role_plan_model import WorkflowRolePlan
from claviger.services.roles.role_manageability_service import is_role_manageable
from claviger.services.roles.role_manager_service import RoleManager


class WorkflowRoleExecutionError(RuntimeError):
    """Base error raised while applying a generic workflow role plan."""


class WorkflowRoleNotFoundError(WorkflowRoleExecutionError):
    """Raised when a planned Discord role disappeared before execution."""


class WorkflowRoleNotManageableError(WorkflowRoleExecutionError):
    """Raised when Claviger cannot safely manage a planned role."""


class WorkflowRoleExecutionPartialError(WorkflowRoleExecutionError):
    """Preserve mutations already applied before Discord failed mid-execution."""

    def __init__(
        self,
        *,
        added_role_ids: tuple[int, ...],
        removed_role_ids: tuple[int, ...],
    ) -> None:
        super().__init__(
            "Workflow role execution stopped after partial Discord mutation."
        )
        self.added_role_ids = added_role_ids
        self.removed_role_ids = removed_role_ids


class WorkflowRoleExecutorService:
    """Preflight and apply a generic workflow role plan."""

    def __init__(
        self,
        role_manager: RoleManager,
    ) -> None:
        self.role_manager = role_manager

    async def execute(
        self,
        member: discord.Member,
        plan: WorkflowRolePlan,
        *,
        reason: str | None = None,
    ) -> WorkflowRoleExecutionResult:
        """Validate every role before applying removals then additions."""

        if not plan.has_changes:
            return WorkflowRoleExecutionResult()

        guild = member.guild
        bot_member = guild.me

        if bot_member is None:
            raise WorkflowRoleExecutionError(
                "Claviger could not resolve its guild member."
            )

        planned_role_ids = tuple(
            dict.fromkeys(
                plan.remove_role_ids + plan.add_role_ids,
            )
        )

        roles_by_id: dict[int, discord.Role] = {}

        for role_id in planned_role_ids:
            role = guild.get_role(
                role_id,
            )

            if role is None:
                raise WorkflowRoleNotFoundError(
                    f"Discord role {role_id} no longer exists."
                )

            if role.is_default() or not is_role_manageable(
                role,
                bot_member,
            ):
                raise WorkflowRoleNotManageableError(
                    f"Discord role {role.name!r} cannot be managed by Claviger."
                )

            roles_by_id[role_id] = role

        added_role_ids: list[int] = []
        removed_role_ids: list[int] = []

        try:
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

        except Exception as error:
            if added_role_ids or removed_role_ids:
                raise WorkflowRoleExecutionPartialError(
                    added_role_ids=tuple(
                        added_role_ids,
                    ),
                    removed_role_ids=tuple(
                        removed_role_ids,
                    ),
                ) from error

            raise

        return WorkflowRoleExecutionResult(
            added_role_ids=tuple(
                added_role_ids,
            ),
            removed_role_ids=tuple(
                removed_role_ids,
            ),
        )
