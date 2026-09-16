"""Compatibility import for the relocated administrative provisioning service."""

from claviger.services.admin.admin_structure_provisioning_service import (
    AdminStructureProvisioningPermissionError,
    AdminStructureProvisioningService,
)

__all__ = [
    "AdminStructureProvisioningPermissionError",
    "AdminStructureProvisioningService",
]
