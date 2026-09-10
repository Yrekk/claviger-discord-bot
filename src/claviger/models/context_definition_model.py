from dataclasses import dataclass
from typing import Literal

ContextValueType = Literal["boolean",]


@dataclass(frozen=True, slots=True)
class ContextDefinition:
    """Describe one guild-specific workflow context."""

    guild_id: int
    context_key: str

    capability_key: str
    value_type: ContextValueType

    role_id: int

    label: str
    description: str | None

    sort_order: int
    enabled: bool
