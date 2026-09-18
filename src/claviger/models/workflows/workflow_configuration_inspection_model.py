from dataclasses import dataclass

from claviger.models.workflows.workflow_definition_model import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class WorkflowConfigurationInspection:
    """Describe persisted facts needed to configure workflows safely.

    Discord discovery remains a separate responsibility. This read model only
    carries application-level reservations and existing workflow bindings that
    must enrich or constrain a configuration attempt.
    """

    guild_id: int
    workflows: tuple[WorkflowDefinition, ...]
    ai_role_id: int | None
    reserved_role_ids: frozenset[int]
    reserved_role_prefixes: tuple[str, ...]
