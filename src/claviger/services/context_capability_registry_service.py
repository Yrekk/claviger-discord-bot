from collections.abc import Iterable

from claviger.models.context_capability_model import ContextCapability

DEFAULT_CONTEXT_CAPABILITIES = (
    ContextCapability(
        capability_key="ai_preference",
        value_type="boolean",
    ),
)


class ContextCapabilityRegistryError(RuntimeError):
    """Base error raised while configuring context capabilities."""


class DuplicateContextCapabilityError(ContextCapabilityRegistryError):
    """Raised when one capability key is registered more than once."""


class ContextCapabilityRegistry:
    """Expose context capabilities implemented by the workflow engine."""

    def __init__(
        self,
        capabilities: Iterable[ContextCapability] = DEFAULT_CONTEXT_CAPABILITIES,
    ) -> None:
        capabilities_by_key: dict[str, ContextCapability] = {}

        for capability in capabilities:
            if capability.capability_key in capabilities_by_key:
                raise DuplicateContextCapabilityError(
                    "Context capability "
                    f"{capability.capability_key!r} is registered more than once."
                )

            capabilities_by_key[capability.capability_key] = capability

        self._capabilities_by_key = capabilities_by_key

    def get(
        self,
        capability_key: str,
    ) -> ContextCapability | None:
        """Return one registered capability, or None when unsupported."""

        return self._capabilities_by_key.get(
            capability_key,
        )

    def contains(
        self,
        capability_key: str,
    ) -> bool:
        """Return whether the engine implements one capability."""

        return capability_key in self._capabilities_by_key

    def all(
        self,
    ) -> tuple[ContextCapability, ...]:
        """Return every registered context capability."""

        return tuple(self._capabilities_by_key.values())
