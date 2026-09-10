from dataclasses import dataclass
from typing import Literal

from claviger.models.catalog_definition_model import CatalogDefinition

WorkflowChannelMode = Literal[
    "restricted",
    "any",
]


@dataclass(frozen=True, slots=True)
class WorkflowCatalogBinding:
    """Bind one catalog definition to a workflow."""

    catalog: CatalogDefinition

    policy_key: str | None

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
