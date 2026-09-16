"""Compatibility import for the relocated workflow configuration repository."""

from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationConflictError,
    WorkflowConfigurationRepository,
)

__all__ = [
    "WorkflowConfigurationConflictError",
    "WorkflowConfigurationRepository",
]
