from collections.abc import Iterable

import discord

from claviger.constants.role_names import AI_OPTION_ROLE_NAME
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.noctis_role_execution_result_model import (
    NoctisRoleExecutionResult,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.adult_access_questionnaire_service import (
    AdultAccessQuestionnaireService,
)
from claviger.services.noctis_role_executor_service import (
    NoctisRoleExecutorService,
)
from claviger.services.noctis_role_planner_service import (
    NoctisRolePlannerService,
)


class NoctisWorkflowError(RuntimeError):
    """Base error raised by the Noctis workflow."""


class NoctisWorkflowDisabledError(NoctisWorkflowError):
    """Raised when adult access management is disabled."""


class NoctisRequiredRoleNotFoundError(NoctisWorkflowError):
    """Raised when a role required by the Noctis workflow is missing."""


class NoctisWorkflowCoordinatorService:
    """Coordinate the complete adult-access workflow."""

    def __init__(
        self,
        questionnaire_service: AdultAccessQuestionnaireService,
        planner_service: NoctisRolePlannerService,
        executor_service: NoctisRoleExecutorService,
    ) -> None:
        self.questionnaire_service = questionnaire_service
        self.planner_service = planner_service
        self.executor_service = executor_service

    async def build_questionnaire(
        self,
        guild: discord.Guild,
        member: discord.Member,
        policy: GuildPolicy,
    ) -> AdultAccessQuestionnaire:
        """Build the questionnaire available to one guild member."""

        self._ensure_workflow_enabled(
            policy,
        )

        return await self.questionnaire_service.build_for_member(
            guild.id,
            member,
        )

    async def apply_selection(
        self,
        guild: discord.Guild,
        member: discord.Member,
        policy: GuildPolicy,
        selected_theme_keys: Iterable[str],
        *,
        include_ai: bool,
    ) -> NoctisRoleExecutionResult:
        """Apply one adult-access questionnaire selection."""

        self._ensure_workflow_enabled(
            policy,
        )

        adult_role = self._find_required_role(
            guild,
            policy.adult_role_name,
        )

        ai_option_role = self._find_required_role(
            guild,
            AI_OPTION_ROLE_NAME,
        )

        # Rebuild from the current database and Discord member state
        # instead of trusting potentially stale UI data.
        questionnaire = await self.questionnaire_service.build_for_member(
            guild.id,
            member,
        )

        plan = self.planner_service.build_plan(
            questionnaire,
            selected_theme_keys,
            include_ai=include_ai,
            member_role_ids=(role.id for role in member.roles),
            adult_role_id=adult_role.id,
            ai_option_role_id=ai_option_role.id,
        )

        return await self.executor_service.execute(
            member,
            plan,
            reason="Noctis questionnaire update",
        )

    @staticmethod
    def _ensure_workflow_enabled(
        policy: GuildPolicy,
    ) -> None:
        """Ensure the guild policy permits Noctis role management."""

        if not policy.role_management_enabled or not policy.adult_access_enabled:
            raise NoctisWorkflowDisabledError(
                "Adult access management is disabled for this guild."
            )

    @staticmethod
    def _find_required_role(
        guild: discord.Guild,
        role_name: str,
    ) -> discord.Role:
        """Resolve one exact Discord role required by the workflow."""

        for role in guild.roles:
            if role.name == role_name:
                return role

        raise NoctisRequiredRoleNotFoundError(
            f"Required Discord role {role_name!r} was not found."
        )
