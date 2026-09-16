"""Compatibility import for the canonical role discovery service."""

from claviger.services.roles.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
    is_manageable_role,
    is_trusted_role,
)

__all__ = [
    "RoleDiscoveryService",
    "RoleHierarchy",
    "is_manageable_role",
    "is_trusted_role",
]
