from dataclasses import dataclass

from claviger.models.workflows.workflow_definition_model import WorkflowDefinition


@dataclass(frozen=True, slots=True)
class GuildAIQuestionnaireOwnerInspection:
    """Describe which workflow owns the guild-wide AI preference question."""

    guild_id: int
    owner_workflow_key: str | None
    workflows: tuple[WorkflowDefinition, ...]
    ai_enabled: bool | None
    ai_role_id: int | None

    @property
    def can_assign_owner(self) -> bool:
        """Return whether the guild AI preference can be exposed by a workflow."""

        return self.ai_enabled is True and self.ai_role_id is not None
