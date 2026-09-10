from dataclasses import dataclass

from claviger.models.context_definition_model import ContextValueType


@dataclass(frozen=True, slots=True)
class QuestionnaireContextQuestion:
    """Describe one editable workflow context question."""

    context_key: str
    capability_key: str
    value_type: ContextValueType

    label: str
    description: str | None

    current_value: bool
