from dataclasses import dataclass

from claviger.models.workflow_definition_model import (
    WorkflowContextBinding,
)


@dataclass(frozen=True, slots=True)
class ResolvedContext:
    """Describe the runtime state of one workflow context for a member."""

    binding: WorkflowContextBinding
    current_value: bool
    role_manageable: bool

    @property
    def context_key(self) -> str:
        """Return the guild-specific context key."""

        return self.binding.context.context_key

    @property
    def capability_key(self) -> str:
        """Return the engine capability represented by this context."""

        return self.binding.context.capability_key

    @property
    def active(self) -> bool:
        """Return whether both the context and its workflow binding are enabled."""

        return self.binding.context.enabled and self.binding.enabled

    @property
    def editable(self) -> bool:
        """Return whether the workflow exposes this context for editing."""

        return self.active and self.binding.interaction_mode == "editable"

    @property
    def can_edit(self) -> bool:
        """Return whether the context is both editable and technically manageable."""

        return self.editable and self.role_manageable
