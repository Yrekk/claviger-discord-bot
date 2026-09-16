import pytest

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowResourceSelection,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.ui.workflows.workflow_configuration_session import (
    WorkflowConfigurationSession,
)


def _discovery() -> WorkflowStructureDiscoveryResult:
    """Create one deterministic workflow UI discovery snapshot."""

    return WorkflowStructureDiscoveryResult(
        categories=(
            WorkflowCategoryCandidate(
                category_id=100,
                category_name="Membres",
                everyone_can_view=True,
                bot_can_view=True,
            ),
        ),
        text_channels=(
            WorkflowTextChannelCandidate(
                channel_id=200,
                channel_name="workflow-info",
                category_id=100,
                everyone_can_view=True,
                everyone_can_send=False,
                bot_can_view=True,
                bot_can_send=True,
            ),
            WorkflowTextChannelCandidate(
                channel_id=201,
                channel_name="salutations",
                category_id=100,
                everyone_can_view=True,
                everyone_can_send=True,
                bot_can_view=True,
                bot_can_send=True,
            ),
        ),
        manageable_roles=(
            WorkflowRoleCandidate(
                role_id=300,
                role_name="Membre",
            ),
            WorkflowRoleCandidate(
                role_id=301,
                role_name="Préférence IA",
            ),
        ),
        can_create_channels=True,
        can_create_roles=True,
    )


def _session() -> WorkflowConfigurationSession:
    """Create one complete deterministic Discord workflow UI session."""

    session = WorkflowConfigurationSession(
        guild_id=123,
        actor_id=42,
        discovery=_discovery(),
    )

    session.title = "Membre"
    session.description = "Gestion du profil membre."
    session.command_name = "membre"
    session.command_description = None
    session.questionnaire_role_prefix = "interest-"

    session.category = WorkflowResourceSelection(
        mode="existing",
        resource_id=100,
    )

    session.management_channel = WorkflowResourceSelection(
        mode="existing",
        resource_id=200,
    )

    session.execution_channel = WorkflowResourceSelection(
        mode="existing",
        resource_id=201,
    )

    session.primary_role = WorkflowResourceSelection(
        mode="existing",
        resource_id=300,
    )

    return session


def test_to_draft_preserves_frontend_neutral_contract() -> None:
    """Convert temporary Discord state into the shared backend draft."""

    session = _session()

    draft = session.to_draft()

    assert draft.guild_id == 123
    assert draft.workflow_key is None
    assert draft.title == "Membre"
    assert draft.command_name == "membre"
    assert draft.questionnaire_role_prefix == "interest-"

    assert draft.category.resource_id == 100
    assert draft.management_channel.resource_id == 200
    assert draft.execution_channel.resource_id == 201
    assert draft.primary_role.resource_id == 300


def test_describe_resource_uses_discovered_cosmetic_name() -> None:
    """Show readable Discord names while keeping IDs as persisted identity."""

    session = _session()

    assert (
        session.describe_resource(
            "category",
        )
        == "`Membres` (`100`)"
    )

    assert (
        session.describe_resource(
            "execution_channel",
        )
        == "`salutations` (`201`)"
    )


def test_describe_created_resource_preserves_requested_name() -> None:
    """Describe pending creation without pretending a Discord ID already exists."""

    session = _session()

    session.execution_channel = WorkflowResourceSelection(
        mode="create",
        name="nouveau-salon",
    )

    assert (
        session.describe_resource(
            "execution_channel",
        )
        == "Créer `nouveau-salon`"
    )


def test_to_draft_rejects_incomplete_structure() -> None:
    """Never send a partial structural configuration to the backend."""

    session = _session()
    session.primary_role = None

    with pytest.raises(
        RuntimeError,
        match="resource configuration is incomplete",
    ):
        session.to_draft()


def test_ai_summary_reuses_persisted_guild_role() -> None:
    """Explain guild-wide AI role reuse without duplicating UI selection."""

    session = _session()

    session.ai_enabled = True
    session.persisted_ai_preference_role_id = 301

    assert session.describe_ai_preference_role() == (
        "Activée — rôle existant `Préférence IA` (`301`)"
    )
