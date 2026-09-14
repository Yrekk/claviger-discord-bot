from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.reporting.event import ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.ui.admin_configuration_view import (
    AdminCategorySelectionView,
    AdminRoutingSelectionView,
)

# ---------------------------------------------------------------------------
# Test fixtures / builders
# ---------------------------------------------------------------------------


def _channel(
    *,
    channel_id: int,
    name: str,
    channel_type: str,
) -> AdminChannelCandidate:
    """Create one deterministic usable ADMIN channel candidate."""

    return AdminChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        channel_type=channel_type,
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )


def _category() -> AdminCategoryCandidate:
    """Create one deterministic ADMIN category used by UI tests."""

    return AdminCategoryCandidate(
        category_id=100,
        category_name="Claviger Admin",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(
            _channel(
                channel_id=200,
                name="admin-commands",
                channel_type="text",
            ),
            _channel(
                channel_id=201,
                name="report-activity",
                channel_type="forum",
            ),
            _channel(
                channel_id=202,
                name="report-error",
                channel_type="forum",
            ),
        ),
    )


def _coordinator() -> Mock:
    """Create a mocked ADMIN configuration coordinator."""

    coordinator = Mock(
        spec=AdminConfigurationCoordinatorService,
    )

    # Every coordinator operation used by the interactive UI is asynchronous.
    coordinator.configure = AsyncMock()
    coordinator.discover_candidates = AsyncMock()
    coordinator.prepare_category = AsyncMock()
    coordinator.save_explicit_routing = AsyncMock()
    coordinator.get_persisted_configuration = AsyncMock()

    return coordinator


def _report_service() -> Mock:
    """Create a mocked report service for ADMIN activation assertions."""

    report_service = Mock(
        spec=ReportService,
    )

    # Report emission is best-effort and asynchronous in production.
    report_service.emit = AsyncMock()

    return report_service


def _interaction(
    *,
    user_id: int = 42,
    guild_id: int = 123,
) -> Mock:
    """Create one deterministic mocked Discord component interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    # Guild identity is required both by routing persistence and reporting.
    guild.id = guild_id
    guild.name = "Laboratorium"
    guild.owner_id = 42

    user = Mock(
        spec=discord.Member,
    )

    # User identity becomes the actor attached to ADMIN activation reports.
    user.id = user_id
    user.display_name = "Yrekk"

    interaction.guild = guild
    interaction.user = user

    # Component callbacks may either respond directly or edit their existing
    # ephemeral message depending on the current stage of the workflow.
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    interaction.edit_original_response = AsyncMock()

    return interaction


def _button_from(
    view: discord.ui.View,
) -> discord.ui.Button:
    """Return the button registered on one deterministic test view."""

    return next(
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Button,
        )
    )


def _select_from(
    view: discord.ui.View,
) -> discord.ui.Select:
    """Return the select menu registered on one deterministic test view."""

    return next(
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Select,
        )
    )


# ---------------------------------------------------------------------------
# Explicit ADMIN routing persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routing_view_persists_complete_explicit_selection() -> None:
    """Persist routing, show human labels and emit the first ADMIN activity."""

    coordinator = _coordinator()
    report_service = _report_service()
    category = _category()

    # Simulate the configuration returned after the coordinator validates and
    # persists the three explicitly selected Discord destinations.
    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    coordinator.save_explicit_routing.return_value = configuration

    view = AdminRoutingSelectionView(
        coordinator=coordinator,
        category=category,
        actor_id=42,
        admin_command_name="experimentum",
        report_service=report_service,
    ).bind_guild(
        123,
    )

    # The three choices normally come from Discord select menus.
    view.command_channel_id = 200
    view.activity_forum_id = 201
    view.error_forum_id = 202

    interaction = _interaction()
    button = _button_from(
        view,
    )

    # Final confirmation is the only point where persistence may occur.
    await button.callback(
        interaction,
    )

    coordinator.save_explicit_routing.assert_awaited_once_with(
        interaction.guild,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    # The human-facing confirmation must display the category name rather than
    # exposing only its Discord snowflake.
    kwargs = interaction.response.edit_message.await_args.kwargs

    assert kwargs["view"] is None
    assert "- Catégorie : `Claviger Admin`" in kwargs["content"]
    assert "- Catégorie : `100`" not in kwargs["content"]
    assert "/experimentum restart" in kwargs["content"]

    # Once persistence succeeds, reporting can immediately resolve the newly
    # configured activity forum. This becomes the first ADMIN activity event.
    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "admin.configuration.activated"
    assert event.severity == ReportSeverity.INFO

    assert event.guild_id == 123
    assert event.guild_label == "Laboratorium"

    assert event.actor_id == 42
    assert event.actor_label == "Yrekk"

    assert event.details is not None

    # Keep both the readable category name and technical routing identifiers in
    # structured diagnostics while the Discord confirmation remains readable.
    assert "Claviger Admin (100)" in event.details
    assert "<#200>" in event.details
    assert "<#201>" in event.details
    assert "<#202>" in event.details


@pytest.mark.asyncio
async def test_routing_view_rejects_same_activity_and_error_forum() -> None:
    """Reject a semantic routing collision before touching persistence."""

    coordinator = _coordinator()

    view = AdminRoutingSelectionView(
        coordinator=coordinator,
        category=_category(),
        actor_id=42,
        admin_command_name="experimentum",
    ).bind_guild(
        123,
    )

    view.command_channel_id = 200
    view.activity_forum_id = 201

    # The same forum cannot simultaneously represent successful activity and
    # incidents because severity routing depends on this semantic distinction.
    view.error_forum_id = 201

    interaction = _interaction()
    button = _button_from(
        view,
    )

    await button.callback(
        interaction,
    )

    # Validation happens before persistence.
    coordinator.save_explicit_routing.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "doivent être différents" in message


# ---------------------------------------------------------------------------
# Explicit ADMIN category selection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_category_selection_prepares_choice_before_routing() -> None:
    """Turn NEEDS_CHOICE into one prepared category and routing view."""

    coordinator = _coordinator()
    category = _category()

    coordinator.prepare_category.return_value = category

    view = AdminCategorySelectionView(
        coordinator=coordinator,
        categories=(category,),
        actor_id=42,
        guild_id=123,
        admin_command_name="experimentum",
    )

    select = _select_from(
        view,
    )

    # discord.py normally fills this internal value from the component payload.
    # Setting it directly keeps this unit test independent from Discord I/O.
    select._values = ["100"]

    interaction = _interaction()

    await select.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once()

    coordinator.prepare_category.assert_awaited_once_with(
        interaction.guild,
        100,
    )

    kwargs = interaction.edit_original_response.await_args.kwargs

    # The category-selection stage must transition to the shared semantic
    # routing UI rather than persist any routing automatically.
    assert isinstance(
        kwargs["view"],
        AdminRoutingSelectionView,
    )

    # Human-readable category identity remains visible during the transition.
    assert "Claviger Admin" in kwargs["content"]
