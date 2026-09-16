"""Compatibility import for the canonical runtime authorization service."""

from claviger.services.runtime.authorization import (
    DEFAULT_TRUSTED_CAPABILITIES,
    AuthorizationService,
    Capability,
)

__all__ = [
    "AuthorizationService",
    "Capability",
    "DEFAULT_TRUSTED_CAPABILITIES",
]
