from dataclasses import dataclass
from typing import Literal

from claviger.models.catalog_definition_model import CatalogDefinition
from claviger.models.context_definition_model import ContextDefinition

WorkflowChannelMode = Literal[
    "restricted",
    "any",
]

WorkflowContextInteractionMode = Literal[
    "editable",
    "read_only",
]


@dataclass(frozen=True, slots=True)
class WorkflowCatalogBinding:
    """Bind one catalog definition to a workflow."""

    catalog: CatalogDefinition

    policy_key: str | None

    sort_order: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class WorkflowContextBinding:
    """Bind one context definition to a workflow."""

    context: ContextDefinition

    interaction_mode: WorkflowContextInteractionMode

    sort_order: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    """Describe one complete guild-specific workflow."""

    guild_id: int
    workflow_key: str

    command_name: str
    command_description: str

    title: str
    description: str | None

    policy_key: str
    channel_mode: WorkflowChannelMode

    sort_order: int
    enabled: bool

    channel_ids: tuple[int, ...]
    catalogs: tuple[WorkflowCatalogBinding, ...]

    contexts: tuple[WorkflowContextBinding, ...] = ()
