import pytest

from claviger.models.context_capability_model import ContextCapability
from claviger.models.context_definition_model import ContextDefinition
from claviger.models.questionnaire_context_question_model import (
    QuestionnaireContextQuestion,
)
from claviger.models.resolved_context_model import ResolvedContext
from claviger.models.workflow_definition_model import (
    WorkflowContextBinding,
)
from claviger.services.context_capability_registry_service import (
    ContextCapabilityRegistry,
)
from claviger.services.questionnaire_context_planner_service import (
    QuestionnaireContextPlanner,
)
from claviger.services.workflow_context_validator_service import (
    ContextNotManageableError,
    WorkflowContextValidator,
)


def create_resolved_context(
    *,
    context_key: str = "ai-content",
    capability_key: str = "ai_preference",
    interaction_mode: str = "editable",
    current_value: bool = False,
    context_enabled: bool = True,
    binding_enabled: bool = True,
    role_manageable: bool = True,
    sort_order: int = 0,
) -> ResolvedContext:
    """Create one resolved context for questionnaire planning tests."""

    context = ContextDefinition(
        guild_id=123,
        context_key=context_key,
        capability_key=capability_key,
        value_type="boolean",
        role_id=100 + sort_order,
        label=f"Configure {context_key}?",
        description=f"Description for {context_key}.",
        sort_order=sort_order,
        enabled=context_enabled,
    )

    binding = WorkflowContextBinding(
        context=context,
        interaction_mode=interaction_mode,  # type: ignore[arg-type]
        sort_order=sort_order,
        enabled=binding_enabled,
    )

    return ResolvedContext(
        binding=binding,
        current_value=current_value,
        role_manageable=role_manageable,
    )


def create_planner() -> QuestionnaireContextPlanner:
    """Create a questionnaire context planner with supported capabilities."""

    registry = ContextCapabilityRegistry(
        (
            ContextCapability(
                capability_key="ai_preference",
                value_type="boolean",
            ),
            ContextCapability(
                capability_key="secondary_preference",
                value_type="boolean",
            ),
        )
    )

    validator = WorkflowContextValidator(
        registry,
    )

    return QuestionnaireContextPlanner(
        validator,
    )


def test_build_questions_returns_editable_context() -> None:
    """Expose one active editable context as a questionnaire question."""

    planner = create_planner()

    result = planner.build_questions(
        (
            create_resolved_context(
                current_value=True,
            ),
        )
    )

    assert result == (
        QuestionnaireContextQuestion(
            context_key="ai-content",
            capability_key="ai_preference",
            value_type="boolean",
            label="Configure ai-content?",
            description="Description for ai-content.",
            current_value=True,
        ),
    )


def test_build_questions_excludes_read_only_context() -> None:
    """Do not ask users to edit read-only workflow contexts."""

    planner = create_planner()

    result = planner.build_questions(
        (
            create_resolved_context(
                interaction_mode="read_only",
            ),
        )
    )

    assert result == ()


def test_build_questions_excludes_disabled_context() -> None:
    """Do not expose disabled context definitions."""

    planner = create_planner()

    result = planner.build_questions(
        (
            create_resolved_context(
                context_enabled=False,
            ),
        )
    )

    assert result == ()


def test_build_questions_excludes_disabled_binding() -> None:
    """Do not expose disabled workflow context bindings."""

    planner = create_planner()

    result = planner.build_questions(
        (
            create_resolved_context(
                binding_enabled=False,
            ),
        )
    )

    assert result == ()


def test_build_questions_preserves_context_order() -> None:
    """Preserve declarative workflow context ordering."""

    planner = create_planner()

    result = planner.build_questions(
        (
            create_resolved_context(
                context_key="ai-content",
                capability_key="ai_preference",
                sort_order=10,
            ),
            create_resolved_context(
                context_key="secondary",
                capability_key="secondary_preference",
                current_value=True,
                sort_order=20,
            ),
        )
    )

    assert tuple(question.context_key for question in result) == (
        "ai-content",
        "secondary",
    )

    assert tuple(question.current_value for question in result) == (
        False,
        True,
    )


def test_build_questions_validates_before_planning() -> None:
    """Never build an editable question backed by an unmanageable role."""

    planner = create_planner()

    with pytest.raises(
        ContextNotManageableError,
    ):
        planner.build_questions(
            (
                create_resolved_context(
                    role_manageable=False,
                ),
            )
        )
