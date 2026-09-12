from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.noctis_role_execution_result_model import (
    NoctisRoleExecutionResult,
)
from claviger.models.noctis_role_plan_model import NoctisRolePlan
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.adult_access_questionnaire_service import (
    AdultAccessQuestionnaireService,
)
from claviger.services.noctis_role_executor_service import (
    NoctisRoleExecutorService,
)
from claviger.services.noctis_role_planner_service import (
    NoctisRolePlannerService,
)
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisRequiredRoleNotFoundError,
    NoctisWorkflowCoordinatorService,
    NoctisWorkflowDisabledError,
)


def create_role(
    *,
    role_id: int,
    name: str,
) -> Mock:
    """Create a mocked Discord role."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name

    return role


def create_guild(
    *roles: Mock,
) -> Mock:
    """Create a mocked Discord guild."""

    guild = Mock(
        spec=discord.Guild,
    )

    guild.id = 123
    guild.roles = list(roles)

    return guild


def create_member(
    *roles: Mock,
) -> Mock:
    """Create a mocked Discord member."""

    member = Mock(
        spec=discord.Member,
    )

    member.roles = list(roles)

    return member


def create_service():
    """Create the workflow coordinator and mocked dependencies."""

    questionnaire_service = Mock(
        spec=AdultAccessQuestionnaireService,
    )
    questionnaire_service.build_for_member = AsyncMock()

    planner_service = Mock(
        spec=NoctisRolePlannerService,
    )

    executor_service = Mock(
        spec=NoctisRoleExecutorService,
    )
    executor_service.execute = AsyncMock()

    service = NoctisWorkflowCoordinatorService(
        questionnaire_service=questionnaire_service,
        planner_service=planner_service,
        executor_service=executor_service,
    )

    return (
        service,
        questionnaire_service,
        planner_service,
        executor_service,
    )


@pytest.mark.asyncio
async def test_build_questionnaire_delegates_to_questionnaire_service() -> None:
    """Build the member questionnaire through the dedicated service."""

    (
        service,
        questionnaire_service,
        _,
        _,
    ) = create_service()

    questionnaire = AdultAccessQuestionnaire(
        themes=(),
        selected_theme_keys=(),
        include_ai=False,
    )

    questionnaire_service.build_for_member.return_value = questionnaire

    guild = create_guild()
    member = create_member()

    result = await service.build_questionnaire(
        guild,
        member,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    questionnaire_service.build_for_member.assert_awaited_once_with(
        123,
        member,
    )

    assert result is questionnaire


@pytest.mark.asyncio
async def test_apply_selection_plans_and_executes_current_state() -> None:
    """Build a fresh plan and execute it for the selected themes."""

    (
        service,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_service()

    adult_role = create_role(
        role_id=1,
        name="Civis Noctis - 18+",
    )

    ai_option_role = create_role(
        role_id=2,
        name="option-ia",
    )

    existing_role = create_role(
        role_id=10,
        name="access-no-ia-yuri",
    )

    guild = create_guild(
        adult_role,
        ai_option_role,
        existing_role,
    )

    member = create_member(
        existing_role,
    )

    questionnaire = AdultAccessQuestionnaire(
        themes=(),
        selected_theme_keys=("yuri",),
        include_ai=False,
    )

    questionnaire_service.build_for_member.return_value = questionnaire

    plan = NoctisRolePlan(
        add_role_ids=(1,),
        remove_role_ids=(),
    )

    planner_service.build_plan.return_value = plan

    execution_result = NoctisRoleExecutionResult(
        added_role_ids=(1,),
        removed_role_ids=(),
    )

    executor_service.execute.return_value = execution_result

    result = await service.apply_selection(
        guild,
        member,
        SUCCUMBRAE_FALLBACK_POLICY,
        ("yuri",),
        include_ai=True,
    )

    questionnaire_service.build_for_member.assert_awaited_once_with(
        123,
        member,
    )

    planner_service.build_plan.assert_called_once_with(
        questionnaire,
        ("yuri",),
        include_ai=True,
        member_role_ids=planner_service.build_plan.call_args.kwargs["member_role_ids"],
        adult_role_id=1,
        ai_option_role_id=2,
    )

    member_role_ids = tuple(
        planner_service.build_plan.call_args.kwargs["member_role_ids"]
    )

    assert member_role_ids == (10,)

    executor_service.execute.assert_awaited_once_with(
        member,
        plan,
        reason="Noctis questionnaire update",
    )

    assert result is execution_result


@pytest.mark.asyncio
async def test_apply_selection_rejects_missing_adult_role() -> None:
    """Reject the workflow when the configured adult role is missing."""

    (
        service,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_service()

    guild = create_guild(
        create_role(
            role_id=2,
            name="option-ia",
        )
    )

    member = create_member()

    with pytest.raises(
        NoctisRequiredRoleNotFoundError,
        match="Civis Noctis",
    ):
        await service.apply_selection(
            guild,
            member,
            SUCCUMBRAE_FALLBACK_POLICY,
            (),
            include_ai=False,
        )

    questionnaire_service.build_for_member.assert_not_awaited()
    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_selection_rejects_missing_ai_option_role() -> None:
    """Reject the workflow when option-ia is missing."""

    (
        service,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_service()

    guild = create_guild(
        create_role(
            role_id=1,
            name="Civis Noctis - 18+",
        )
    )

    member = create_member()

    with pytest.raises(
        NoctisRequiredRoleNotFoundError,
        match="option-ia",
    ):
        await service.apply_selection(
            guild,
            member,
            SUCCUMBRAE_FALLBACK_POLICY,
            (),
            include_ai=False,
        )

    questionnaire_service.build_for_member.assert_not_awaited()
    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_workflow_rejects_disabled_adult_access() -> None:
    """Reject Noctis when adult access is disabled by guild policy."""

    (
        service,
        questionnaire_service,
        planner_service,
        executor_service,
    ) = create_service()

    disabled_policy = replace(
        SUCCUMBRAE_FALLBACK_POLICY,
        adult_access_enabled=False,
    )

    guild = create_guild()
    member = create_member()

    with pytest.raises(
        NoctisWorkflowDisabledError,
        match="disabled",
    ):
        await service.build_questionnaire(
            guild,
            member,
            disabled_policy,
        )

    questionnaire_service.build_for_member.assert_not_awaited()
    planner_service.build_plan.assert_not_called()
    executor_service.execute.assert_not_awaited()
