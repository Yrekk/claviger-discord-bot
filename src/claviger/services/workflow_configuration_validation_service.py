"""Compatibility import for the canonical workflow validation service."""

from claviger.services.workflows.workflow_configuration_validation_service import (
    COMMAND_NAME_PATTERN,
    MAX_COMMAND_DESCRIPTION_LENGTH,
    MAX_DISCORD_RESOURCE_NAME_LENGTH,
    MAX_ROLE_PREFIX_LENGTH,
    MAX_WORKFLOW_TITLE_LENGTH,
    WORKFLOW_KEY_PATTERN,
    InvalidWorkflowCommandNameError,
    InvalidWorkflowKeyError,
    InvalidWorkflowResourceSelectionError,
    InvalidWorkflowRolePrefixError,
    WorkflowChannelCollisionError,
    WorkflowConfigurationValidationError,
    WorkflowConfigurationValidationService,
)

__all__ = [
    "COMMAND_NAME_PATTERN",
    "MAX_COMMAND_DESCRIPTION_LENGTH",
    "MAX_DISCORD_RESOURCE_NAME_LENGTH",
    "MAX_ROLE_PREFIX_LENGTH",
    "MAX_WORKFLOW_TITLE_LENGTH",
    "WORKFLOW_KEY_PATTERN",
    "InvalidWorkflowCommandNameError",
    "InvalidWorkflowKeyError",
    "InvalidWorkflowResourceSelectionError",
    "InvalidWorkflowRolePrefixError",
    "WorkflowChannelCollisionError",
    "WorkflowConfigurationValidationError",
    "WorkflowConfigurationValidationService",
]
