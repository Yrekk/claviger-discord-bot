import pytest

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowResourceSelection,
)
from claviger.services.workflows.workflow_configuration_validation_service import (
    InvalidWorkflowCommandNameError,
    InvalidWorkflowResourceSelectionError,
    InvalidWorkflowRolePrefixError,
    WorkflowChannelCollisionError,
    WorkflowConfigurationValidationService,
)

# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------


def _existing(
    resource_id: int,
) -> WorkflowResourceSelection:
    """Create one deterministic existing-resource selection."""

    return WorkflowResourceSelection(
        mode="existing",
        resource_id=resource_id,
    )


def _create(
    name: str,
) -> WorkflowResourceSelection:
    """Create one deterministic resource-creation selection."""

    return WorkflowResourceSelection(
        mode="create",
        name=name,
    )


def _draft(
    **overrides: object,
) -> WorkflowConfigurationDraft:
    """Create one valid workflow configuration draft with optional overrides."""

    values: dict[str, object] = {
        "guild_id": 123,
        "workflow_key": None,
        "title": "Membre",
        "description": None,
        "command_name": "membre",
        "command_description": None,
        "category": _create("Membres"),
        "management_channel": _create("membre-admin"),
        "execution_channel": _create("salutations"),
        "primary_role": _create("Membre"),
        "questionnaire_role_prefix": "interest-",
        "ai_enabled": False,
    }
    values.update(overrides)
    return WorkflowConfigurationDraft(**values)


def test_validate_normalizes_create_configuration() -> None:
    service = WorkflowConfigurationValidationService()
    result = service.validate(
        _draft(title="  Membre  ", questionnaire_role_prefix="  interest-  ")
    )
    assert result.workflow_key == "membre"
    assert result.title == "Membre"
    assert result.command_name == "membre"
    assert result.command_description == "Gère le workflow Membre."
    assert result.category.name == "Membres"
    assert result.management_channel.name == "membre-admin"
    assert result.execution_channel.name == "salutations"
    assert result.primary_role.name == "Membre"
    assert result.questionnaire_role_prefix == "interest-"
    assert result.ai_enabled is False


def test_validate_accepts_existing_discord_resources() -> None:
    service = WorkflowConfigurationValidationService()
    result = service.validate(
        _draft(
            workflow_key="member-profile",
            category=_existing(100),
            management_channel=_existing(200),
            execution_channel=_existing(201),
            primary_role=_existing(300),
            ai_enabled=True,
        )
    )
    assert result.workflow_key == "member-profile"
    assert result.category.resource_id == 100
    assert result.management_channel.resource_id == 200
    assert result.execution_channel.resource_id == 201
    assert result.primary_role.resource_id == 300
    assert result.ai_enabled is True


def test_validate_preserves_explicit_command_description() -> None:
    service = WorkflowConfigurationValidationService()
    result = service.validate(
        _draft(command_description="Configure tes centres d'intérêt.")
    )
    assert result.command_description == "Configure tes centres d'intérêt."


def test_existing_resource_requires_positive_discord_id() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(InvalidWorkflowResourceSelectionError):
        service.validate(
            _draft(
                category=WorkflowResourceSelection(mode="existing", resource_id=None)
            )
        )


def test_created_resource_rejects_existing_discord_id() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(InvalidWorkflowResourceSelectionError):
        service.validate(
            _draft(
                primary_role=WorkflowResourceSelection(
                    mode="create", resource_id=300, name="Membre"
                )
            )
        )


def test_created_resource_requires_non_empty_name() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(InvalidWorkflowResourceSelectionError):
        service.validate(_draft(execution_channel=_create("   ")))


@pytest.mark.parametrize(
    "command_name",
    ("Membre", "member command", "/membre", ""),
)
def test_invalid_command_names_are_rejected(command_name: str) -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(InvalidWorkflowCommandNameError):
        service.validate(_draft(command_name=command_name))


def test_questionnaire_prefix_cannot_be_blank() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(InvalidWorkflowRolePrefixError):
        service.validate(_draft(questionnaire_role_prefix="   "))


def test_existing_management_and_execution_channels_must_differ() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(WorkflowChannelCollisionError):
        service.validate(
            _draft(
                management_channel=_existing(200), execution_channel=_existing(200)
            )
        )


def test_created_management_and_execution_channels_must_differ() -> None:
    service = WorkflowConfigurationValidationService()
    with pytest.raises(WorkflowChannelCollisionError):
        service.validate(
            _draft(
                management_channel=_create("workflow"),
                execution_channel=_create("WORKFLOW"),
            )
        )
