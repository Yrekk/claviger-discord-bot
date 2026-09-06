from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)
from claviger.services.noctis_role_planner_service import (
    NoctisRolePlannerService,
)


def create_access(
    *,
    role_id: int,
    access_key: str,
) -> AdultAccess:
    """Create one publicly ready adult access."""

    return AdultAccess(
        guild_id=123,
        role_id=role_id,
        role_name=f"access-{access_key}",
        catalog_key=access_key,
        channel_id=role_id + 1000,
        channel_name=access_key,
        label=access_key,
        description="Description",
        emoji=None,
        sort_order=10,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


def create_questionnaire() -> AdultAccessQuestionnaire:
    """Create Yuri and BDSM logical themes."""

    workflow_service = AdultAccessWorkflowService()

    themes = workflow_service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-yuri",
            ),
            create_access(
                role_id=11,
                access_key="ia-yuri",
            ),
            create_access(
                role_id=20,
                access_key="no-ia-bdsm",
            ),
            create_access(
                role_id=21,
                access_key="ia-bdsm",
            ),
        )
    )

    return AdultAccessQuestionnaire(
        themes=themes,
        selected_theme_keys=(),
        include_ai=False,
    )


def create_service() -> NoctisRolePlannerService:
    """Create the Noctis role planner."""

    return NoctisRolePlannerService(
        workflow_service=AdultAccessWorkflowService(),
    )


def test_build_plan_adds_base_roles_without_ai() -> None:
    """Add adult and base access roles when IA is disabled."""

    plan = create_service().build_plan(
        create_questionnaire(),
        ("yuri", "bdsm"),
        include_ai=False,
        member_role_ids=(),
        adult_role_id=1,
        ai_option_role_id=2,
    )

    assert plan.add_role_ids == (
        1,
        20,
        10,
    )

    assert plan.remove_role_ids == ()


def test_build_plan_adds_ai_variants_and_option_role() -> None:
    """Add IA variants and the global option role when requested."""

    plan = create_service().build_plan(
        create_questionnaire(),
        ("yuri",),
        include_ai=True,
        member_role_ids=(1,),
        adult_role_id=1,
        ai_option_role_id=2,
    )

    assert plan.add_role_ids == (
        10,
        11,
        2,
    )

    assert plan.remove_role_ids == ()


def test_build_plan_removes_old_accesses_and_ai_option() -> None:
    """Remove deselected managed roles while preserving unrelated roles."""

    plan = create_service().build_plan(
        create_questionnaire(),
        ("bdsm",),
        include_ai=False,
        member_role_ids=(
            1,
            2,
            10,
            11,
            999,
        ),
        adult_role_id=1,
        ai_option_role_id=2,
    )

    assert plan.add_role_ids == (20,)

    assert plan.remove_role_ids == (
        2,
        10,
        11,
    )

    assert 999 not in plan.remove_role_ids


def test_build_plan_is_empty_when_member_already_matches() -> None:
    """Return an empty plan when the member already has desired roles."""

    plan = create_service().build_plan(
        create_questionnaire(),
        ("yuri",),
        include_ai=True,
        member_role_ids=(
            1,
            2,
            10,
            11,
            999,
        ),
        adult_role_id=1,
        ai_option_role_id=2,
    )

    assert plan.add_role_ids == ()
    assert plan.remove_role_ids == ()
    assert plan.change_count == 0
    assert plan.has_changes is False
