from unittest.mock import Mock

import pytest

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.services.member_role_planner_service import (
    MemberRolePlannerService,
    UnknownMemberInterestError,
)


def create_interest(
    *,
    key: str,
    role_id: int,
) -> Mock:
    """Create a catalog interest for planner tests."""

    interest = Mock(
        spec=RoleChannelCatalogEntry,
    )

    interest.catalog_key = key
    interest.role_id = role_id

    return interest


def create_questionnaire() -> MemberInterestQuestionnaire:
    """Create a deterministic member-interest questionnaire."""

    return MemberInterestQuestionnaire(
        interests=(
            create_interest(
                key="musicae",
                role_id=10,
            ),
            create_interest(
                key="codex",
                role_id=20,
            ),
            create_interest(
                key="ludus",
                role_id=30,
            ),
        ),
        selected_interest_keys=(),
    )


def test_member_planner_adds_member_and_selected_interests() -> None:
    """Add the base member role and selected missing interests."""

    planner = MemberRolePlannerService()

    plan = planner.build_plan(
        questionnaire=create_questionnaire(),
        selected_interest_keys=(
            "codex",
            "musicae",
        ),
        member_role_ids=set(),
        member_role_id=100,
    )

    assert plan.add_role_ids == (
        100,
        10,
        20,
    )

    assert plan.remove_role_ids == ()
    assert plan.change_count == 3
    assert plan.has_changes is True


def test_member_planner_removes_only_deselected_managed_interests() -> None:
    """Never remove unrelated Discord roles."""

    planner = MemberRolePlannerService()

    plan = planner.build_plan(
        questionnaire=create_questionnaire(),
        selected_interest_keys=("codex",),
        member_role_ids={
            100,
            10,
            20,
            999,
        },
        member_role_id=100,
    )

    assert plan.add_role_ids == ()

    assert plan.remove_role_ids == (10,)

    assert 999 not in plan.remove_role_ids


def test_member_planner_does_nothing_when_state_matches_selection() -> None:
    """Produce an empty plan when Discord already matches the request."""

    planner = MemberRolePlannerService()

    plan = planner.build_plan(
        questionnaire=create_questionnaire(),
        selected_interest_keys=(
            "musicae",
            "codex",
        ),
        member_role_ids={
            100,
            10,
            20,
        },
        member_role_id=100,
    )

    assert plan.add_role_ids == ()
    assert plan.remove_role_ids == ()
    assert plan.change_count == 0
    assert plan.has_changes is False


def test_member_planner_allows_empty_interest_selection() -> None:
    """Allow someone to be a member without subscribing to interests."""

    planner = MemberRolePlannerService()

    plan = planner.build_plan(
        questionnaire=create_questionnaire(),
        selected_interest_keys=(),
        member_role_ids={
            10,
            20,
            999,
        },
        member_role_id=100,
    )

    assert plan.add_role_ids == (100,)

    assert plan.remove_role_ids == (
        10,
        20,
    )

    assert 999 not in plan.remove_role_ids


def test_member_planner_rejects_unknown_interest() -> None:
    """Reject selections that were not exposed by the questionnaire."""

    planner = MemberRolePlannerService()

    with pytest.raises(
        UnknownMemberInterestError,
        match="unknown-interest",
    ):
        planner.build_plan(
            questionnaire=create_questionnaire(),
            selected_interest_keys=("unknown-interest",),
            member_role_ids=set(),
            member_role_id=100,
        )
