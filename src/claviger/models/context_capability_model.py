from dataclasses import dataclass

from claviger.models.context_definition_model import ContextValueType


@dataclass(frozen=True, slots=True)
class ContextCapability:
    """Describe one workflow context capability supported by the engine."""

    capability_key: str
    value_type: ContextValueType
