import discord

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.member_role_execution_result_model import (
    MemberRoleExecutionResult,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.member_interest_questionnaire_service import (
    MemberInterestQuestionnaireService,
)
from claviger.services.member_role_executor_service import (
    MemberRoleExecutorService,
)
from claviger.services.member_role_planner_service import (
    MemberRolePlannerService,
)


class MemberWorkflowError(RuntimeError):
    """Base error raised by the member role workflow."""


class MemberRoleManagementDisabledError(MemberWorkflowError):
    """Raised when member role management is disabled by guild policy."""


class MemberBaseRoleNotFoundError(MemberWorkflowError):
    """Raised when the configured member role does not exist."""


class MemberWorkflowCoordinatorService:
    """Coordinate the complete /membre role-management workflow."""

    def __init__(
        self,
        questionnaire_service: MemberInterestQuestionnaireService,
        planner_service: MemberRolePlannerService,
        executor_service: MemberRoleExecutorService,
    ) -> None:
        self.questionnaire_service = questionnaire_service
        self.planner_service = planner_service
        self.executor_service = executor_service

    async def build_questionnaire(
        self,
        guild: discord.Guild,
        member: discord.Member,
        policy: GuildPolicy,
    ) -> MemberInterestQuestionnaire:
        """Build the current member questionnaire."""

        self._ensure_enabled(
            policy,
        )

        self._resolve_member_role(
            guild,
            policy,
        )

        return await self.questionnaire_service.build_for_member(
            guild_id=guild.id,
            member=member,
        )

    async def apply_selection(
        self,
        guild: discord.Guild,
        member: discord.Member,
        policy: GuildPolicy,
        selected_interest_keys: tuple[str, ...],
    ) -> MemberRoleExecutionResult:
        """Reconcile Discord member roles with a submitted selection."""

        self._ensure_enabled(
            policy,
        )

        member_role = self._resolve_member_role(
            guild,
            policy,
        )

        # Rebuild the questionnaire at submission time.
        #
        # The catalog or Discord state may have changed while the modal
        # was open, so the submitted keys must be validated against the
        # current publicly available interests rather than stale UI data.
        questionnaire = await self.questionnaire_service.build_for_member(
            guild_id=guild.id,
            member=member,
        )

        current_role_ids = {role.id for role in member.roles}

        plan = self.planner_service.build_plan(
            questionnaire=questionnaire,
            selected_interest_keys=selected_interest_keys,
            member_role_ids=current_role_ids,
            member_role_id=member_role.id,
        )

        return await self.executor_service.execute(
            member,
            plan,
            reason="Member questionnaire update",
        )

    @staticmethod
    def _ensure_enabled(
        policy: GuildPolicy,
    ) -> None:
        """Ensure member role management is enabled by guild policy."""

        if not policy.role_management_enabled:
            raise MemberRoleManagementDisabledError(
                "Member role management is disabled for this guild."
            )

    @staticmethod
    def _resolve_member_role(
        guild: discord.Guild,
        policy: GuildPolicy,
    ) -> discord.Role:
        """Resolve the configured member role by its exact policy name."""

        role = discord.utils.get(
            guild.roles,
            name=policy.member_role_name,
        )

        if role is None:
            raise MemberBaseRoleNotFoundError(
                (f"Configured member role does not exist: {policy.member_role_name!r}.")
            )

        return role
