import pytest

from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireCatalog,
    WorkflowQuestionnaireCatalogSubmission,
    WorkflowQuestionnaireOption,
    WorkflowQuestionnaireSubmission,
)
from claviger.services.workflows.workflow_role_planner_service import (
    WorkflowQuestionnaireSubmissionError,
    WorkflowRolePlannerService,
)


def _questionnaire(
    *,
    ai_editable: bool = True,
    ai_preference: bool = True,
) -> WorkflowQuestionnaire:
    return WorkflowQuestionnaire(
        guild_id=123,
        workflow_key="noctis",
        command_name="noctis",
        title="Noctis",
        description=None,
        primary_role_id=300,
        catalogs=(
            WorkflowQuestionnaireCatalog(
                catalog_key="access",
                display_name="Accès",
                description=None,
                options=(
                    WorkflowQuestionnaireOption(
                        catalog_key="access",
                        entry_key="casino",
                        label="Casino",
                        description=None,
                        emoji=None,
                        target_role_id=502,
                        selected=True,
                    ),
                    WorkflowQuestionnaireOption(
                        catalog_key="access",
                        entry_key="studio",
                        label="Studio",
                        description=None,
                        emoji=None,
                        target_role_id=503,
                        selected=False,
                    ),
                ),
            ),
        ),
        managed_catalog_role_ids=(
            501,
            502,
            503,
        ),
        ai_enabled=True,
        ai_role_id=900,
        ai_editable=ai_editable,
        ai_preference=ai_preference,
    )


def _submission(
    *,
    selected: tuple[str, ...] = ("casino",),
    ai_preference: bool | None = True,
) -> WorkflowQuestionnaireSubmission:
    return WorkflowQuestionnaireSubmission(
        catalogs=(
            WorkflowQuestionnaireCatalogSubmission(
                catalog_key="access",
                visible_entry_keys=(
                    "casino",
                    "studio",
                ),
                selected_entry_keys=selected,
            ),
        ),
        ai_preference=ai_preference,
    )


def test_plan_swaps_variant_roles_and_manages_ai_only_for_owner() -> None:
    """Replace obsolete variants, add primary role and update the global AI role."""

    plan = WorkflowRolePlannerService().build_plan(
        questionnaire=_questionnaire(),
        submission=_submission(
            selected=("casino",),
            ai_preference=True,
        ),
        member_role_ids={
            501,
        },
    )

    assert plan.add_role_ids == (
        300,
        502,
        900,
    )
    assert plan.remove_role_ids == (
        501,
    )


def test_non_owner_never_mutates_ai_role() -> None:
    """Other workflows consume AI state without owning the preference role."""

    plan = WorkflowRolePlannerService().build_plan(
        questionnaire=_questionnaire(
            ai_editable=False,
            ai_preference=True,
        ),
        submission=_submission(
            ai_preference=None,
        ),
        member_role_ids={
            300,
            502,
            900,
        },
    )

    assert plan.add_role_ids == ()
    assert plan.remove_role_ids == ()


def test_stale_visible_options_are_rejected_before_planning() -> None:
    """Do not interpret a stale form as a destructive deselection."""

    submission = WorkflowQuestionnaireSubmission(
        catalogs=(
            WorkflowQuestionnaireCatalogSubmission(
                catalog_key="access",
                visible_entry_keys=("casino",),
                selected_entry_keys=("casino",),
            ),
        ),
        ai_preference=True,
    )

    with pytest.raises(
        WorkflowQuestionnaireSubmissionError,
        match="options changed",
    ):
        WorkflowRolePlannerService().build_plan(
            questionnaire=_questionnaire(),
            submission=submission,
            member_role_ids=set(),
        )
