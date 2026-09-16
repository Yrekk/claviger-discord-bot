"""Compatibility imports for relocated context capability registry services."""

from claviger.services.context.context_capability_registry_service import (
    DEFAULT_CONTEXT_CAPABILITIES,
    ContextCapabilityRegistry,
    ContextCapabilityRegistryError,
    DuplicateContextCapabilityError,
)

__all__ = [
    "DEFAULT_CONTEXT_CAPABILITIES",
    "ContextCapabilityRegistry",
    "ContextCapabilityRegistryError",
    "DuplicateContextCapabilityError",
]
