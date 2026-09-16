from dataclasses import dataclass

from claviger.models.workflows.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)


@dataclass(frozen=True, slots=True)
class WorkflowStructureProvisioningResult:
    """Describe one completed Discord workflow provisioning pass."""

    guild_id: int

    # This is the final stable identity set ready for SQLite persistence.
    configuration: ResolvedWorkflowConfiguration

    # Mutation metadata remains separate from persisted workflow semantics.
    # Frontends and reporting can therefore explain what Claviger changed
    # without making provisioning history part of the workflow definition.
    created_category_id: int | None = None
    created_channel_ids: tuple[int, ...] = ()
    created_role_ids: tuple[int, ...] = ()

    category_permissions_repaired: bool = False
    repaired_channel_ids: tuple[int, ...] = ()
