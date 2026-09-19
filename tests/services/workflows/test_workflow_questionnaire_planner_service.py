from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
    CatalogTargetVariant,
)
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.services.workflows.workflow_questionnaire_planner_service import (
    WorkflowQuestionnairePlannerService,
)


def _target(
    role_id: int,
    variant: CatalogTargetVariant,
    *,
    available: bool = True,
) -> CatalogEntryTarget:
    return CatalogEntryTarget(
        guild_id=123,
        catalog_key="access",
        entry_key="casino",
        role_id=role_id,
        role_name=f"role-{role_id}",
        channel_id=role_id + 1000,
        channel_name=f"channel-{role_id}",
        variant=variant,
        enabled=available,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


def _entry(
    key: str,
    *targets: CatalogEntryTarget,
    sort_order: int = 0,
) -> CatalogEntry:
    return CatalogEntry(
        guild_id=123,
        catalog_key="access",
        entry_key=key,
        label=key.title(),
        description=None,
        emoji=None,
        sort_order=sort_order,
        enabled=True,
        targets=tuple(targets),
    )


def _workflow() -> WorkflowDefinition:
    catalog = CatalogDefinition(
        guild_id=123,
        catalog_key="access",
        role_prefix="access-",
        display_name="Accès",
        entry_name="Accès",
        description=None,
        sort_order=0,
        enabled=True,
    )
    return WorkflowDefinition(
        guild_id=123,
        workflow_key="noctis",
        command_name="noctis",
        command_description="Configure tes accès.",
        title="Noctis",
        description=None,
        policy_key="noctis",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(200,),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=catalog,
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        primary_role_id=300,
    )


def test_questionnaire_uses_member_ai_state_and_restores_logical_selection() -> None:
    """Keep the no-AI baseline and add the AI target for one logical choice."""

    planner = WorkflowQuestionnairePlannerService()
    no_ai = _target(501, "no_ai")
    ai = _target(502, "ai")
    base = _target(
        503,
        "base",
    )

    result = planner.build(
        workflow=_workflow(),
        entries_by_catalog={
            "access": (
                _entry("casino", no_ai, ai),
                _entry("generic", base, sort_order=20),
            ),
        },
        member_role_ids={
            502,
            900,
        },
        ai_enabled=True,
        ai_role_id=900,
        owner_workflow_key="noctis",
    )

    assert result.ai_editable is True
    assert result.ai_preference is True
    assert tuple(option.entry_key for option in result.catalogs[0].options) == (
        "casino",
        "generic",
    )
    casino = result.catalogs[0].options[0]
    assert casino.target_role_ids == (
        501,
        502,
    )
    assert casino.selected is True


def test_questionnaire_supports_ai_only_and_no_ai_only_entries() -> None:
    """Keep no-AI singletons visible and add AI-only choices when IA is active."""

    planner = WorkflowQuestionnairePlannerService()

    result = planner.build(
        workflow=_workflow(),
        entries_by_catalog={
            "access": (
                _entry("ai-only", _target(601, "ai")),
                _entry("no-ai-only", _target(602, "no_ai")),
            ),
        },
        member_role_ids=set(),
        ai_enabled=True,
        ai_role_id=900,
        owner_workflow_key=None,
    )

    assert tuple(option.entry_key for option in result.catalogs[0].options) == (
        "no-ai-only",
    )

    result_ai = planner.build(
        workflow=_workflow(),
        entries_by_catalog={
            "access": (
                _entry("ai-only", _target(601, "ai")),
                _entry("no-ai-only", _target(602, "no_ai")),
            ),
        },
        member_role_ids={900},
        ai_enabled=True,
        ai_role_id=900,
        owner_workflow_key=None,
    )

    assert tuple(option.entry_key for option in result_ai.catalogs[0].options) == (
        "ai-only",
        "no-ai-only",
    )
    assert result_ai.catalogs[0].options[0].target_role_ids == (
        601,
    )
    assert result_ai.catalogs[0].options[1].target_role_ids == (
        602,
    )


def test_owner_can_preview_questionnaire_for_new_ai_preference() -> None:
    """Resolve targets against the preference selected by the unique owner workflow."""

    planner = WorkflowQuestionnairePlannerService()

    result = planner.build(
        workflow=_workflow(),
        entries_by_catalog={
            "access": (
                _entry(
                    "casino",
                    _target(501, "no_ai"),
                    _target(502, "ai"),
                ),
            ),
        },
        member_role_ids=set(),
        ai_enabled=True,
        ai_role_id=900,
        owner_workflow_key="noctis",
        requested_ai_preference=True,
    )

    assert result.ai_preference is True
    assert result.catalogs[0].options[0].target_role_ids == (
        501,
        502,
    )


def test_ai_pair_is_hidden_when_one_required_target_is_unavailable() -> None:
    """Fail closed instead of applying only half of an IA-enabled pair."""

    planner = WorkflowQuestionnairePlannerService()

    result = planner.build(
        workflow=_workflow(),
        entries_by_catalog={
            "access": (
                _entry(
                    "casino",
                    _target(501, "no_ai"),
                    _target(502, "ai", available=False),
                ),
            ),
        },
        member_role_ids={
            900,
        },
        ai_enabled=True,
        ai_role_id=900,
        owner_workflow_key=None,
    )

    assert result.catalogs == ()
