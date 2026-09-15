import pytest

from claviger.models.workflow_configuration_model import (
    WorkflowConfigurationDraft,
    WorkflowResourceSelection,
)
from claviger.models.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.services.workflow_configuration_reconciliation_service import (
    WorkflowAiPreferenceRoleRequiredError,
    WorkflowCategoryMismatchError,
    WorkflowConfigurationReconciliationError,
    WorkflowConfigurationReconciliationService,
    WorkflowMutationPermissionError,
    WorkflowRoleCollisionError,
)
from claviger.services.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationError,
    WorkflowConfigurationValidationService,
)

# ---------------------------------------------------------------------------
# Shared configuration builders
# ---------------------------------------------------------------------------


def _existing(
    resource_id: int,
) -> WorkflowResourceSelection:
    """Create one stable existing-resource selection."""

    return WorkflowResourceSelection(
        mode="existing",
        resource_id=resource_id,
    )


def _create(
    name: str,
) -> WorkflowResourceSelection:
    """Create one stable resource-creation selection."""

    return WorkflowResourceSelection(
        mode="create",
        name=name,
    )


def _draft(
    **overrides: object,
) -> WorkflowConfigurationDraft:
    """Create one valid existing-resource workflow draft."""

    values: dict[str, object] = {
        "guild_id": 123,
        "workflow_key": "member",
        "title": "Membre",
        "description": None,
        "command_name": "membre",
        "command_description": "Gère ton profil membre.",
        "category": _existing(
            100,
        ),
        "management_channel": _existing(
            200,
        ),
        "execution_channel": _existing(
            201,
        ),
        "primary_role": _existing(
            300,
        ),
        "questionnaire_role_prefix": "interest-",
        "ai_enabled": False,
        "ai_preference_role": None,
    }

    values.update(
        overrides,
    )

    return WorkflowConfigurationDraft(
        **values,
    )


def _category(
    *,
    category_id: int = 100,
    bot_can_view: bool = True,
) -> WorkflowCategoryCandidate:
    """Create one discovered workflow category."""

    return WorkflowCategoryCandidate(
        category_id=category_id,
        category_name="Communauté",
        everyone_can_view=True,
        bot_can_view=bot_can_view,
    )


def _channel(
    *,
    channel_id: int,
    category_id: int | None = 100,
    everyone_can_send: bool = True,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> WorkflowTextChannelCandidate:
    """Create one discovered workflow text channel."""

    return WorkflowTextChannelCandidate(
        channel_id=channel_id,
        channel_name=f"channel-{channel_id}",
        category_id=category_id,
        everyone_can_view=True,
        everyone_can_send=everyone_can_send,
        bot_can_view=bot_can_view,
        bot_can_send=bot_can_send,
    )


def _role(
    role_id: int,
) -> WorkflowRoleCandidate:
    """Create one manageable discovered Discord role."""

    return WorkflowRoleCandidate(
        role_id=role_id,
        role_name=f"Role {role_id}",
    )


def _discovery(
    *,
    categories: tuple[WorkflowCategoryCandidate, ...] | None = None,
    channels: tuple[WorkflowTextChannelCandidate, ...] | None = None,
    roles: tuple[WorkflowRoleCandidate, ...] | None = None,
    can_create_channels: bool = True,
    can_create_roles: bool = True,
) -> WorkflowStructureDiscoveryResult:
    """Create one deterministic workflow discovery snapshot."""

    return WorkflowStructureDiscoveryResult(
        categories=((_category(),) if categories is None else categories),
        text_channels=(
            (
                _channel(
                    channel_id=200,
                    everyone_can_send=False,
                ),
                _channel(
                    channel_id=201,
                ),
            )
            if channels is None
            else channels
        ),
        manageable_roles=(
            (
                _role(
                    300,
                ),
                _role(
                    301,
                ),
            )
            if roles is None
            else roles
        ),
        can_create_channels=can_create_channels,
        can_create_roles=can_create_roles,
    )


def _validate(
    draft: WorkflowConfigurationDraft,
):
    """Normalize one draft before reconciliation."""

    return WorkflowConfigurationValidationService().validate(
        draft,
    )


# ---------------------------------------------------------------------------
# Generic Discord reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_accepts_existing_workflow_resources() -> None:
    """Accept resources that still match current Discord state."""

    service = WorkflowConfigurationReconciliationService()

    result = service.reconcile(
        configuration=_validate(
            _draft(),
        ),
        discovery=_discovery(),
    )

    assert result.category.resource_id == 100
    assert result.management_channel.resource_id == 200
    assert result.execution_channel.resource_id == 201
    assert result.primary_role.resource_id == 300


def test_reconcile_accepts_full_creation_on_empty_guild() -> None:
    """Allow a complete workflow structure to be created from scratch."""

    service = WorkflowConfigurationReconciliationService()

    configuration = _validate(
        _draft(
            category=_create(
                "Membres",
            ),
            management_channel=_create(
                "workflow-info",
            ),
            execution_channel=_create(
                "salutations",
            ),
            primary_role=_create(
                "Membre",
            ),
        )
    )

    result = service.reconcile(
        configuration=configuration,
        discovery=_discovery(
            categories=(),
            channels=(),
            roles=(),
        ),
    )

    assert result.category.name == "Membres"
    assert result.management_channel.name == "workflow-info"
    assert result.execution_channel.name == "salutations"
    assert result.primary_role.name == "Membre"


def test_existing_channel_must_belong_to_selected_category() -> None:
    """Reject accidental cross-category workflow routing."""

    service = WorkflowConfigurationReconciliationService()

    discovery = _discovery(
        channels=(
            _channel(
                channel_id=200,
                category_id=999,
                everyone_can_send=False,
            ),
            _channel(
                channel_id=201,
            ),
        )
    )

    with pytest.raises(
        WorkflowCategoryMismatchError,
        match="management channel",
    ):
        service.reconcile(
            configuration=_validate(
                _draft(),
            ),
            discovery=discovery,
        )


def test_new_category_cannot_silently_move_existing_channels() -> None:
    """Require channels to be created with a newly created workflow category."""

    service = WorkflowConfigurationReconciliationService()

    with pytest.raises(
        WorkflowCategoryMismatchError,
        match="has not been created",
    ):
        service.reconcile(
            configuration=_validate(
                _draft(
                    category=_create(
                        "Membres",
                    ),
                )
            ),
            discovery=_discovery(),
        )


def test_creation_requires_channel_management_permission() -> None:
    """Fail before provisioning when Discord channel mutation is unavailable."""

    service = WorkflowConfigurationReconciliationService()

    with pytest.raises(
        WorkflowMutationPermissionError,
        match="workflow category",
    ):
        service.reconcile(
            configuration=_validate(
                _draft(
                    category=_create(
                        "Membres",
                    ),
                    management_channel=_create(
                        "workflow-info",
                    ),
                    execution_channel=_create(
                        "salutations",
                    ),
                )
            ),
            discovery=_discovery(
                can_create_channels=False,
            ),
        )


def test_existing_management_channel_requires_repair_permission() -> None:
    """Reject a writable management channel when Claviger cannot lock it."""

    service = WorkflowConfigurationReconciliationService()

    discovery = _discovery(
        channels=(
            _channel(
                channel_id=200,
                everyone_can_send=True,
            ),
            _channel(
                channel_id=201,
            ),
        ),
        can_create_channels=False,
    )

    with pytest.raises(
        WorkflowMutationPermissionError,
        match="management channel",
    ):
        service.reconcile(
            configuration=_validate(
                _draft(),
            ),
            discovery=discovery,
        )


def test_existing_primary_role_must_be_manageable() -> None:
    """Reject roles that Claviger cannot safely assign or remove."""

    service = WorkflowConfigurationReconciliationService()

    with pytest.raises(
        WorkflowConfigurationReconciliationError,
    ):
        service.reconcile(
            configuration=_validate(
                _draft(),
            ),
            discovery=_discovery(
                roles=(
                    _role(
                        301,
                    ),
                ),
            ),
        )


# ---------------------------------------------------------------------------
# AI preference capability reconciliation
# ---------------------------------------------------------------------------


def test_reconcile_reuses_persisted_ai_preference_role() -> None:
    """Reuse the guild-wide AI capability without asking the frontend again."""

    service = WorkflowConfigurationReconciliationService()

    result = service.reconcile(
        configuration=_validate(
            _draft(
                ai_enabled=True,
            )
        ),
        discovery=_discovery(),
        persisted_ai_preference_role_id=301,
    )

    assert result.ai_preference_role == WorkflowResourceSelection(
        mode="existing",
        resource_id=301,
    )


def test_first_ai_workflow_requires_preference_role() -> None:
    """Require one role identity when AI is enabled for the guild first time."""

    service = WorkflowConfigurationReconciliationService()

    with pytest.raises(
        WorkflowAiPreferenceRoleRequiredError,
    ):
        service.reconcile(
            configuration=_validate(
                _draft(
                    ai_enabled=True,
                )
            ),
            discovery=_discovery(),
            persisted_ai_preference_role_id=None,
        )


def test_first_ai_workflow_can_request_role_creation() -> None:
    """Allow the first AI-enabled workflow to provision its capability role."""

    service = WorkflowConfigurationReconciliationService()

    result = service.reconcile(
        configuration=_validate(
            _draft(
                ai_enabled=True,
                ai_preference_role=_create(
                    "Préférence IA",
                ),
            )
        ),
        discovery=_discovery(),
    )

    assert result.ai_preference_role == WorkflowResourceSelection(
        mode="create",
        name="Préférence IA",
    )


def test_primary_and_ai_roles_must_be_distinct() -> None:
    """Prevent the membership role from also encoding AI preference."""

    service = WorkflowConfigurationReconciliationService()

    with pytest.raises(
        WorkflowRoleCollisionError,
    ):
        service.reconcile(
            configuration=_validate(
                _draft(
                    ai_enabled=True,
                    ai_preference_role=_existing(
                        300,
                    ),
                )
            ),
            discovery=_discovery(),
        )


def test_validation_rejects_ai_role_when_ai_is_disabled() -> None:
    """Reject contradictory frontend configuration before reconciliation."""

    with pytest.raises(
        WorkflowConfigurationValidationError,
        match="when AI is disabled",
    ):
        _validate(
            _draft(
                ai_enabled=False,
                ai_preference_role=_existing(
                    301,
                ),
            )
        )
