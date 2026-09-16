"""Compatibility import for the relocated administrative coordinator service."""

from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)

__all__ = ["AdminConfigurationCoordinatorService"]
