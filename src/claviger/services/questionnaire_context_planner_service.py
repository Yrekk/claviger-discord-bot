from collections.abc import Sequence

from claviger.models.questionnaire_context_question_model import (
    QuestionnaireContextQuestion,
)
from claviger.models.resolved_context_model import ResolvedContext
from claviger.services.workflow_context_validator_service import (
    WorkflowContextValidator,
)


class QuestionnaireContextPlanner:
    """Build questionnaire questions from resolved workflow contexts."""

    def __init__(
        self,
        validator: WorkflowContextValidator,
    ) -> None:
        self.validator = validator

    def build_questions(
        self,
        contexts: Sequence[ResolvedContext],
    ) -> tuple[QuestionnaireContextQuestion, ...]:
        """Return every active editable context as a questionnaire question."""

        self.validator.validate(
            contexts,
        )

        return tuple(
            QuestionnaireContextQuestion(
                context_key=resolved.context_key,
                capability_key=resolved.capability_key,
                value_type=resolved.binding.context.value_type,
                label=resolved.binding.context.label,
                description=resolved.binding.context.description,
                current_value=resolved.current_value,
            )
            for resolved in contexts
            if resolved.active and resolved.editable
        )
