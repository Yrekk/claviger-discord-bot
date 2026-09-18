import re

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowConfigurationSpec,
    WorkflowResourceSelection,
)

# Slash-command names intentionally use a conservative subset of Discord's
# accepted syntax. Stable workflow keys follow the same readable convention.
COMMAND_NAME_PATTERN = re.compile(r"^[a-z0-9_-]{1,32}$")

WORKFLOW_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

MAX_DISCORD_RESOURCE_NAME_LENGTH = 100
MAX_WORKFLOW_TITLE_LENGTH = 100
MAX_COMMAND_DESCRIPTION_LENGTH = 100
MAX_ROLE_PREFIX_LENGTH = 100


class WorkflowConfigurationValidationError(ValueError):
    """Base error raised when a workflow configuration draft is invalid."""


class InvalidWorkflowResourceSelectionError(WorkflowConfigurationValidationError):
    """Raised when an existing/create resource choice is inconsistent."""


class InvalidWorkflowCommandNameError(WorkflowConfigurationValidationError):
    """Raised when a configured slash-command name is invalid."""


class InvalidWorkflowKeyError(WorkflowConfigurationValidationError):
    """Raised when the stable workflow key is invalid."""


class InvalidWorkflowRolePrefixError(WorkflowConfigurationValidationError):
    """Raised when questionnaire role discovery has no usable prefix."""


class WorkflowChannelCollisionError(WorkflowConfigurationValidationError):
    """Raised when management and execution resolve to the same channel."""


class WorkflowConfigurationValidationService:
    """Validate and normalize frontend-neutral workflow configuration drafts."""

    def validate(
        self,
        draft: WorkflowConfigurationDraft,
    ) -> WorkflowConfigurationSpec:
        """Return a normalized spec or reject an unsafe configuration."""

        if draft.guild_id <= 0:
            raise WorkflowConfigurationValidationError(
                "Discord guild ID must be greater than zero."
            )

        title = self._require_text(
            draft.title,
            field_name="workflow title",
            max_length=MAX_WORKFLOW_TITLE_LENGTH,
        )

        description = self._optional_text(
            draft.description,
        )

        command_name = draft.command_name.strip()

        if not COMMAND_NAME_PATTERN.fullmatch(
            command_name,
        ):
            raise InvalidWorkflowCommandNameError(
                "Workflow command names must contain only lowercase letters, "
                "numbers, underscores or hyphens and be at most 32 characters."
            )

        workflow_key = (
            command_name if draft.workflow_key is None else draft.workflow_key.strip()
        )

        if not WORKFLOW_KEY_PATTERN.fullmatch(
            workflow_key,
        ):
            raise InvalidWorkflowKeyError(
                "Workflow keys must start with a lowercase letter or number, "
                "contain only lowercase letters, numbers, underscores or "
                "hyphens, and be at most 64 characters."
            )

        command_description = self._normalize_command_description(
            draft.command_description,
            title=title,
        )

        category = self._validate_resource(
            draft.category,
            resource_label="category",
        )

        management_channel = self._validate_resource(
            draft.management_channel,
            resource_label="management channel",
        )

        execution_channel = self._validate_resource(
            draft.execution_channel,
            resource_label="execution channel",
        )

        primary_role = self._validate_resource(
            draft.primary_role,
            resource_label="primary role",
        )

        self._reject_channel_collision(
            management_channel,
            execution_channel,
        )

        questionnaire_role_prefix = draft.questionnaire_role_prefix.strip()

        if (
            not questionnaire_role_prefix
            or len(questionnaire_role_prefix) > MAX_ROLE_PREFIX_LENGTH
        ):
            raise InvalidWorkflowRolePrefixError(
                "Questionnaire role prefix must contain between 1 and "
                f"{MAX_ROLE_PREFIX_LENGTH} characters."
            )

        return WorkflowConfigurationSpec(
            guild_id=draft.guild_id,
            workflow_key=workflow_key,
            title=title,
            description=description,
            command_name=command_name,
            command_description=command_description,
            category=category,
            management_channel=management_channel,
            execution_channel=execution_channel,
            primary_role=primary_role,
            questionnaire_role_prefix=questionnaire_role_prefix,
        )

    @staticmethod
    def _require_text(
        value: str,
        *,
        field_name: str,
        max_length: int,
    ) -> str:
        """Normalize one mandatory human-readable text value."""

        normalized = value.strip()

        if not normalized:
            raise WorkflowConfigurationValidationError(f"{field_name} cannot be empty.")

        if len(normalized) > max_length:
            raise WorkflowConfigurationValidationError(
                f"{field_name} cannot exceed {max_length} characters."
            )

        return normalized

    @staticmethod
    def _optional_text(
        value: str | None,
    ) -> str | None:
        """Normalize optional text while converting blank input to None."""

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    def _normalize_command_description(
        self,
        value: str | None,
        *,
        title: str,
    ) -> str:
        """Return an explicit or deterministic Discord command description."""

        if value is not None:
            normalized = value.strip()

            if not normalized:
                raise WorkflowConfigurationValidationError(
                    "Command description cannot be blank when provided."
                )

            if len(normalized) > MAX_COMMAND_DESCRIPTION_LENGTH:
                raise WorkflowConfigurationValidationError(
                    "Command description cannot exceed "
                    f"{MAX_COMMAND_DESCRIPTION_LENGTH} characters."
                )

            return normalized

        # Keep creation simple for the Discord UI. The future Web UI may expose
        # this as an advanced editable field without changing the backend.
        generated = f"Gère le workflow {title}."

        if len(generated) <= MAX_COMMAND_DESCRIPTION_LENGTH:
            return generated

        return "Gère ce workflow."

    def _validate_resource(
        self,
        selection: WorkflowResourceSelection,
        *,
        resource_label: str,
    ) -> WorkflowResourceSelection:
        """Validate one existing-or-create resource choice."""

        if selection.mode == "existing":
            if selection.resource_id is None or selection.resource_id <= 0:
                raise InvalidWorkflowResourceSelectionError(
                    f"Existing {resource_label} requires a positive Discord ID."
                )

            if selection.name is not None:
                raise InvalidWorkflowResourceSelectionError(
                    f"Existing {resource_label} must not carry a creation name."
                )

            return WorkflowResourceSelection(
                mode="existing",
                resource_id=selection.resource_id,
            )

        if selection.mode == "create":
            if selection.resource_id is not None:
                raise InvalidWorkflowResourceSelectionError(
                    f"New {resource_label} must not already have a Discord ID."
                )

            if selection.name is None:
                raise InvalidWorkflowResourceSelectionError(
                    f"New {resource_label} requires a name."
                )

            normalized_name = selection.name.strip()

            if not normalized_name:
                raise InvalidWorkflowResourceSelectionError(
                    f"New {resource_label} requires a non-empty name."
                )

            if len(normalized_name) > MAX_DISCORD_RESOURCE_NAME_LENGTH:
                raise InvalidWorkflowResourceSelectionError(
                    f"New {resource_label} name cannot exceed "
                    f"{MAX_DISCORD_RESOURCE_NAME_LENGTH} characters."
                )

            return WorkflowResourceSelection(
                mode="create",
                name=normalized_name,
            )

        raise InvalidWorkflowResourceSelectionError(
            f"Unsupported resource selection mode: {selection.mode!r}."
        )

    @staticmethod
    def _reject_channel_collision(
        management_channel: WorkflowResourceSelection,
        execution_channel: WorkflowResourceSelection,
    ) -> None:
        """Keep private management and public execution semantics distinct."""

        if (
            management_channel.mode == "existing"
            and execution_channel.mode == "existing"
            and management_channel.resource_id == execution_channel.resource_id
        ):
            raise WorkflowChannelCollisionError(
                "Management and execution channels must be different."
            )

        if (
            management_channel.mode == "create"
            and execution_channel.mode == "create"
            and management_channel.name.casefold() == execution_channel.name.casefold()
        ):
            raise WorkflowChannelCollisionError(
                "Management and execution channels must use different names."
            )
