from collections.abc import Sequence

from claviger.models.resolved_context_model import ResolvedContext
from claviger.services.context_capability_registry_service import (
    ContextCapabilityRegistry,
)


class WorkflowContextValidationError(RuntimeError):
    """Base error raised for invalid resolved workflow contexts."""


class UnsupportedContextCapabilityError(WorkflowContextValidationError):
    """Raised when a workflow uses a capability unknown to the engine."""


class ContextCapabilityTypeMismatchError(WorkflowContextValidationError):
    """Raised when a context value type conflicts with its capability."""


class ContextNotManageableError(WorkflowContextValidationError):
    """Raised when an editable context cannot be mutated safely."""


class WorkflowContextValidator:
    """Validate resolved contexts before workflow planning."""

    def __init__(
        self,
        registry: ContextCapabilityRegistry,
    ) -> None:
        self.registry = registry

    def validate(
        self,
        contexts: Sequence[ResolvedContext],
    ) -> None:
        """Reject active workflow contexts the engine cannot safely use."""

        for resolved in contexts:
            if not resolved.active:
                continue

            context = resolved.binding.context

            capability = self.registry.get(
                context.capability_key,
            )

            if capability is None:
                raise UnsupportedContextCapabilityError(
                    "Context "
                    f"{context.context_key!r} uses unsupported capability "
                    f"{context.capability_key!r}."
                )

            if context.value_type != capability.value_type:
                raise ContextCapabilityTypeMismatchError(
                    "Context "
                    f"{context.context_key!r} uses value type "
                    f"{context.value_type!r}, but capability "
                    f"{context.capability_key!r} requires "
                    f"{capability.value_type!r}."
                )

            if resolved.editable and not resolved.role_manageable:
                raise ContextNotManageableError(
                    "Editable context "
                    f"{context.context_key!r} references Discord role "
                    f"{context.role_id}, which Claviger cannot manage."
                )
