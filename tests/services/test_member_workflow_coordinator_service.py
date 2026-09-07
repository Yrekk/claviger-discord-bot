from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.member_role_execution_result_model import (
    MemberRoleExecutionResult,
)
from claviger.models.member_role_plan_model import MemberRolePlan
from claviger.policies.default_policy import (
    SAFE_DEFAULT_POLICY,
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.member_interest_questionnaire_service import (
    MemberInterestQuestionnaireService,
)
from claviger.services.member_role_executor_service import (
    MemberRoleExecutorService,
)
from claviger.services.member_role_planner_service import (
    MemberRolePlannerService,
)
from claviger.services.member_workflow_coordinator_service import (
    MemberBaseRoleNotFoundError,
    MemberRoleManagementDisabledError,
    MemberWorkflowCoordinatorService,
)


def create_role(
    *,
    role_id: int,
    name: str,
) -> Mock:
    """Create a Discord role for coordinator tests."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name

    return role


def create_guild(
    *roles: discord.Role,
) -> Mock:
    """Create a Discord guild exposing the requested roles."""

    guild = Mock(
        spec=discord.Guild,
    )

    guild.id = 123
    guild.roles = list(
        roles,
    )

    return guild


def create_member(
    *roles: discord.Role,
) -> Mock:
    """Create a Discord member with the requested current roles."""

    member = Mock(
        spec=discord.Member,
    )

    member.roles = list(
        roles,
    )

    return member


def create_coordinator() -> tuple[
    MemberWorkflowCoordinatorService,
    Mock,
    Mock,
    Mock,
]:
    """Create the coordinator with mocked workflow dependencies."""

    questionnaire_service = Mock(
        spec=MemberInterestQuestionnaireService,
    )

    questionnaire_service.build_for_member = AsyncMock()

    planner_service = Mock(
        spec=MemberRolePlannerService,
    )

    planner_service.build_plan = Mock()

    executor_service = Mock(
        spec=MemberRoleExecutorService,
    )

    executor_service.execute = AsyncMock()

    coordinator = MemberWorkflowCoordinatorService(
        questionnaire_service=questionnaire_service,
        planner_service=planner_service,
        executor_service=executor_service,
    )

    return (
        coordinator,
        questionnaire_service,
        planner_service,
        executor_service,
    )


@pytest.mark.asyncio
async def test_member_coordinator_builds_current_questionnaire() -> None:
    """Build the questionnaire through the configured catalog service."""

    member_role = create_role(
        role_id=100,
        name="Membre",
    )

    guild = create_guild(
        member_role,
    )

    member = create_member()

    questionnaire = MemberInterestQuestionnaire(
        interests=(),
        selected_interest_keys=(),
    )

    (
        coordinator,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_coordinator()

    questionnaire_service.build_for_member.return_value = questionnaire

    result = await coordinator.build_questionnaire(
        guild,
        member,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    assert result is questionnaire

    questionnaire_service.build_for_member.assert_awaited_once_with(
        guild_id=123,
        member=member,
    )

    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_coordinator_rejects_disabled_role_management() -> None:
    """Reject the workflow when guild policy disables role management."""

    guild = create_guild()
    member = create_member()

    (
        coordinator,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_coordinator()

    with pytest.raises(
        MemberRoleManagementDisabledError,
        match="disabled",
    ):
        await coordinator.build_questionnaire(
            guild,
            member,
            SAFE_DEFAULT_POLICY,
        )

    questionnaire_service.build_for_member.assert_not_awaited()
    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_coordinator_requires_configured_member_role() -> None:
    """Reject the workflow when the configured base member role is absent."""

    guild = create_guild(
        create_role(
            role_id=999,
            name="Other role",
        )
    )

    member = create_member()

    (
        coordinator,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_coordinator()

    with pytest.raises(
        MemberBaseRoleNotFoundError,
        match="Membre",
    ):
        await coordinator.build_questionnaire(
            guild,
            member,
            SUCCUMBRAE_FALLBACK_POLICY,
        )

    questionnaire_service.build_for_member.assert_not_awaited()
    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_coordinator_rebuilds_state_before_applying_selection() -> None:
    """Plan submitted changes from the member's current Discord state."""

    member_role = create_role(
        role_id=100,
        name="Membre",
    )

    existing_interest = create_role(
        role_id=10,
        name="interest-musicae",
    )

    unrelated_role = create_role(
        role_id=999,
        name="Modo",
    )

    guild = create_guild(
        member_role,
        existing_interest,
        unrelated_role,
    )

    member = create_member(
        existing_interest,
        unrelated_role,
    )

    questionnaire = MemberInterestQuestionnaire(
        interests=(),
        selected_interest_keys=(),
    )

    plan = MemberRolePlan(
        add_role_ids=(100,),
    )

    execution_result = MemberRoleExecutionResult(
        added_role_ids=(100,),
        removed_role_ids=(),
    )

    (
        coordinator,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_coordinator()

    questionnaire_service.build_for_member.return_value = questionnaire
    planner_service.build_plan.return_value = plan
    executor_service.execute.return_value = execution_result

    result = await coordinator.apply_selection(
        guild,
        member,
        SUCCUMBRAE_FALLBACK_POLICY,
        ("musicae",),
    )

    assert result is execution_result

    questionnaire_service.build_for_member.assert_awaited_once_with(
        guild_id=123,
        member=member,
    )

    planner_service.build_plan.assert_called_once_with(
        questionnaire=questionnaire,
        selected_interest_keys=("musicae",),
        member_role_ids={
            10,
            999,
        },
        member_role_id=100,
    )

    executor_service.execute.assert_awaited_once_with(
        member,
        plan,
        reason="Member questionnaire update",
    )
