from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowRoleCandidate,
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)
from claviger.ui.workflows.workflow_configuration_session import (
    WorkflowConfigurationSession,
)
from claviger.ui.workflows.workflow_configuration_view import (
    WorkflowConfigurationStartView,
    WorkflowDetectedStructureChannelView,
    WorkflowDetectedStructureView,
    _detected_structures_content,
    _selected_structure_content,
    _structure_channel_choice_content,
    run_workflow_configuration,
)

# ---------------------------------------------------------------------------
# Discovery fixtures
# ---------------------------------------------------------------------------


def _category(
    *,
    category_id: int,
    name: str,
) -> WorkflowCategoryCandidate:
    """Create one deterministic discovered Discord category."""

    return WorkflowCategoryCandidate(
        category_id=category_id,
        category_name=name,
        everyone_can_view=True,
        bot_can_view=True,
    )


def _channel(
    *,
    channel_id: int,
    name: str,
    category_id: int,
    everyone_can_send: bool,
    application_role_send_override: bool | None = None,
) -> WorkflowTextChannelCandidate:
    """Create one deterministic discovered Discord text channel."""

    return WorkflowTextChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        category_id=category_id,
        everyone_can_view=True,
        everyone_can_send=everyone_can_send,
        bot_can_view=True,
        bot_can_send=True,
        application_role_send_override=application_role_send_override,
    )


def _porta_discovery() -> WorkflowStructureDiscoveryResult:
    """Reproduce the structural shape used by the existing Succumbrae workflow."""

    category = _category(
        category_id=100,
        name="PORTA",
    )

    vestibulum = _channel(
        channel_id=200,
        name="vestibulum",
        category_id=100,
        everyone_can_send=False,
        application_role_send_override=True,
    )

    salutationes = _channel(
        channel_id=201,
        name="salutationes",
        category_id=100,
        everyone_can_send=True,
    )

    index = _channel(
        channel_id=202,
        name="index",
        category_id=100,
        everyone_can_send=False,
        application_role_send_override=True,
    )

    candidate = WorkflowStructureCandidate(
        category=category,
        protected_channels=(
            index,
            vestibulum,
        ),
        interactive_channels=(salutationes,),
    )

    return WorkflowStructureDiscoveryResult(
        categories=(category,),
        text_channels=(
            index,
            salutationes,
            vestibulum,
        ),
        manageable_roles=(
            WorkflowRoleCandidate(
                role_id=300,
                role_name="Primary Role",
            ),
        ),
        can_create_channels=True,
        can_create_roles=True,
        workflow_candidates=(candidate,),
    )


def _simple_discovery() -> WorkflowStructureDiscoveryResult:
    """Create one structure with no ambiguous channel choice."""

    category = _category(
        category_id=110,
        name="STRUCTURE-A",
    )

    protected = _channel(
        channel_id=210,
        name="protected",
        category_id=110,
        everyone_can_send=False,
        application_role_send_override=True,
    )

    interactive = _channel(
        channel_id=211,
        name="interactive",
        category_id=110,
        everyone_can_send=True,
    )

    candidate = WorkflowStructureCandidate(
        category=category,
        protected_channels=(protected,),
        interactive_channels=(interactive,),
    )

    return WorkflowStructureDiscoveryResult(
        categories=(category,),
        text_channels=(
            protected,
            interactive,
        ),
        manageable_roles=(),
        can_create_channels=True,
        can_create_roles=True,
        workflow_candidates=(candidate,),
    )


def _empty_discovery() -> WorkflowStructureDiscoveryResult:
    """Create one guild snapshot without recognized workflow structure."""

    return WorkflowStructureDiscoveryResult(
        categories=(),
        text_channels=(),
        manageable_roles=(),
        can_create_channels=True,
        can_create_roles=True,
        workflow_candidates=(),
    )


def _session(
    discovery: WorkflowStructureDiscoveryResult,
) -> WorkflowConfigurationSession:
    """Create one deterministic UI session over a discovery snapshot."""

    return WorkflowConfigurationSession(
        guild_id=123,
        actor_id=42,
        discovery=discovery,
    )


# ---------------------------------------------------------------------------
# Session integration with structural discovery
# ---------------------------------------------------------------------------


def test_selecting_porta_reuses_category_and_unique_interactive_channel() -> None:
    """Reuse deterministic resources and leave only ambiguous ones unresolved."""

    session = _session(
        _porta_discovery(),
    )

    candidate = session.select_structure_candidate(
        category_id=100,
    )

    assert candidate.category.category_name == "PORTA"

    assert session.selected_structure_category_id == 100

    assert session.category is not None
    assert session.category.mode == "existing"
    assert session.category.resource_id == 100

    # Two protected channels exist: the UI must ask the human.
    assert session.management_channel is None

    # Only one interactive channel exists: no decision is necessary.
    assert session.execution_channel is not None
    assert session.execution_channel.mode == "existing"
    assert session.execution_channel.resource_id == 201

    assert session.has_complete_selected_structure() is False


def test_human_can_resolve_porta_protected_channel_ambiguity() -> None:
    """Allow the human to identify the management channel among protected ones."""

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    session.select_structure_channel(
        resource="management_channel",
        channel_id=200,
    )

    assert session.management_channel is not None
    assert session.management_channel.resource_id == 200

    assert session.execution_channel is not None
    assert session.execution_channel.resource_id == 201

    assert session.has_complete_selected_structure() is True


def test_human_can_choose_index_if_that_is_the_intended_protected_channel() -> None:
    """Discovery never decides which protected channel carries workflow semantics."""

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    session.select_structure_channel(
        resource="management_channel",
        channel_id=202,
    )

    assert session.management_channel is not None
    assert session.management_channel.resource_id == 202
    assert session.has_complete_selected_structure() is True


def test_structure_channel_choice_rejects_channel_outside_candidate() -> None:
    """Never accept a Discord channel not supplied by the selected structure."""

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    with pytest.raises(
        ValueError,
        match="does not belong",
    ):
        session.select_structure_channel(
            resource="management_channel",
            channel_id=999,
        )


def test_simple_structure_is_complete_immediately_after_selection() -> None:
    """Avoid useless questions when discovery leaves no ambiguity."""

    session = _session(
        _simple_discovery(),
    )

    session.select_structure_candidate(
        category_id=110,
    )

    assert session.category is not None
    assert session.category.resource_id == 110

    assert session.management_channel is not None
    assert session.management_channel.resource_id == 210

    assert session.execution_channel is not None
    assert session.execution_channel.resource_id == 211

    assert session.has_complete_selected_structure() is True


def test_clear_selected_structure_returns_session_to_manual_mode() -> None:
    """Allow explicit abandonment of detected-structure reuse."""

    session = _session(
        _simple_discovery(),
    )

    session.select_structure_candidate(
        category_id=110,
    )

    session.clear_selected_structure()

    assert session.selected_structure_category_id is None
    assert session.category is None
    assert session.management_channel is None
    assert session.execution_channel is None


# ---------------------------------------------------------------------------
# Discord presentation
# ---------------------------------------------------------------------------


def test_detected_structure_content_exposes_backend_result_without_ids() -> None:
    """Display discovered names without exposing internal Discord snowflakes."""

    session = _session(
        _porta_discovery(),
    )

    content = _detected_structures_content(
        session,
    )

    assert "PORTA" in content
    assert "#vestibulum" in content
    assert "#salutationes" in content
    assert "#index" in content

    assert "200" not in content
    assert "201" not in content
    assert "202" not in content


def test_selected_structure_summary_does_not_assign_channel_semantics() -> None:
    """Present protected and interactive groups without guessing their purpose."""

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    content = _selected_structure_content(
        session,
    )

    assert "PORTA" in content
    assert "Salons protégés" in content
    assert "#vestibulum" in content
    assert "#index" in content
    assert "Salons interactifs" in content
    assert "#salutationes" in content


def test_porta_management_choice_explains_why_human_selection_is_required() -> None:
    """Explain ambiguity without allowing the UI to resolve it itself."""

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    content = _structure_channel_choice_content(
        session,
        resource="management_channel",
    )

    assert "Choix nécessaire" in content
    assert "salon de gestion / règles" in content
    assert "Plusieurs salons protégés" in content


def test_detected_structure_view_exposes_candidate_selector() -> None:
    """Expose backend candidates as UI choices without rediscovering anything."""

    coordinator = MagicMock()

    session = _session(
        _porta_discovery(),
    )

    view = WorkflowDetectedStructureView(
        coordinator=coordinator,
        session=session,
        admin_command_name="application",
    )

    selects = [
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Select,
        )
    ]

    assert len(selects) == 1

    select = selects[0]

    assert len(select.options) == 1
    assert select.options[0].label == "PORTA"
    assert select.options[0].value == "100"


def test_ambiguous_porta_structure_exposes_protected_channel_selector() -> None:
    """Expose the two protected channels after the category is chosen."""

    coordinator = MagicMock()

    session = _session(
        _porta_discovery(),
    )

    session.select_structure_candidate(
        category_id=100,
    )

    view = WorkflowDetectedStructureChannelView(
        coordinator=coordinator,
        session=session,
        resource="management_channel",
        admin_command_name="application",
    )

    selects = [
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Select,
        )
    ]

    assert len(selects) == 1

    values = {option.value for option in selects[0].options}

    assert values == {
        "200",
        "202",
    }


def test_detected_structure_content_mentions_existing_workflow_binding() -> None:
    """Tell the operator that a reusable structure already serves a workflow."""

    discovery = _porta_discovery()
    candidate = discovery.workflow_candidates[0]

    discovery = WorkflowStructureDiscoveryResult(
        categories=discovery.categories,
        text_channels=discovery.text_channels,
        manageable_roles=discovery.manageable_roles,
        can_create_channels=discovery.can_create_channels,
        can_create_roles=discovery.can_create_roles,
        workflow_candidates=(
            WorkflowStructureCandidate(
                category=candidate.category,
                protected_channels=candidate.protected_channels,
                interactive_channels=candidate.interactive_channels,
                configured_command_names=(
                    "membre",
                ),
            ),
        ),
    )

    session = WorkflowConfigurationSession(
        guild_id=123,
        actor_id=42,
        discovery=discovery,
    )

    content = _detected_structures_content(
        session,
    )

    assert "/membre" in content
    assert "déjà configuré" in content


# ---------------------------------------------------------------------------
# Public workflow configuration entry point
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_workflow_configuration_prefers_detected_structures() -> None:
    """Present structural candidates before any metadata modal can be opened."""

    discovery = _porta_discovery()

    coordinator = MagicMock()
    coordinator.discover_resources = AsyncMock(
        return_value=discovery,
    )

    guild = SimpleNamespace(
        id=123,
    )

    followup = SimpleNamespace(
        send=AsyncMock(),
    )

    interaction = SimpleNamespace(
        guild=guild,
        user=SimpleNamespace(
            id=42,
        ),
        followup=followup,
    )

    await run_workflow_configuration(
        interaction,
        coordinator=coordinator,
        admin_command_name="application",
    )

    coordinator.discover_resources.assert_awaited_once_with(
        guild,
    )

    followup.send.assert_awaited_once()

    call = followup.send.await_args

    assert call.kwargs["ephemeral"] is True
    assert isinstance(
        call.kwargs["view"],
        WorkflowDetectedStructureView,
    )

    assert "PORTA" in call.args[0]


@pytest.mark.asyncio
async def test_run_workflow_configuration_uses_manual_start_when_no_pattern_exists() -> (
    None
):
    """Keep manual creation available when backend discovery finds no structure."""

    discovery = _empty_discovery()

    coordinator = MagicMock()
    coordinator.discover_resources = AsyncMock(
        return_value=discovery,
    )

    guild = SimpleNamespace(
        id=123,
    )

    followup = SimpleNamespace(
        send=AsyncMock(),
    )

    interaction = SimpleNamespace(
        guild=guild,
        user=SimpleNamespace(
            id=42,
        ),
        followup=followup,
    )

    await run_workflow_configuration(
        interaction,
        coordinator=coordinator,
        admin_command_name="application",
    )

    followup.send.assert_awaited_once()

    call = followup.send.await_args

    assert isinstance(
        call.kwargs["view"],
        WorkflowConfigurationStartView,
    )

    assert "Aucune structure" in call.args[0]
