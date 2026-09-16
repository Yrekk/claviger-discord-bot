"""Compatibility import for the canonical role manageability service."""

from claviger.services.roles.role_manageability_service import (
    is_role_manageable,
)

__all__ = ["is_role_manageable"]
