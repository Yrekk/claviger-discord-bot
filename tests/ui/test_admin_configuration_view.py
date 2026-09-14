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
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.ui.admin_configuration_view import (
    AdminCategorySelectionView,
    AdminRoutingSelectionView,
)


def _channel(
    *,
    channel_id: int,
    name: str,
    channel_type: str,
) -> AdminChannelCandidate:
    """Create one usable ADMIN channel candidate."""

    return AdminChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        channel_type=channel_type,
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )


def _category() -> AdminCategoryCandidate:
    """Create one deterministic ADMIN category."""

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
    coordinator.configure = AsyncMock()
    coordinator.discover_candidates = AsyncMock()
    coordinator.prepare_category = AsyncMock()
    coordinator.save_explicit_routing = AsyncMock()
    coordinator.get_persisted_configuration = AsyncMock()

    return coordinator


def _interaction(
    *,
    user_id: int = 42,
    guild_id: int = 123,
) -> Mock:
    """Create one mocked component interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = guild_id
    guild.owner_id = 42

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    interaction.edit_original_response = AsyncMock()

    return interaction


@pytest.mark.asyncio
async def test_routing_view_persists_complete_explicit_selection() -> None:
    """Persist the three semantic destinations only on final confirmation."""

    coordinator = _coordinator()
    category = _category()

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
    ).bind_guild(
        123,
    )

    view.command_channel_id = 200
    view.activity_forum_id = 201
    view.error_forum_id = 202

    interaction = _interaction()

    button = next(
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Button,
        )
    )

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

    kwargs = interaction.response.edit_message.await_args.kwargs

    assert kwargs["view"] is None
    assert "/experimentum restart" in kwargs["content"]


@pytest.mark.asyncio
async def test_routing_view_rejects_same_activity_and_error_forum() -> None:
    """Reject a semantic collision before touching persistence."""

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
    view.error_forum_id = 201

    interaction = _interaction()

    button = next(
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Button,
        )
    )

    await button.callback(
        interaction,
    )

    coordinator.save_explicit_routing.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "doivent être différents" in message


@pytest.mark.asyncio
async def test_category_selection_prepares_choice_before_routing() -> None:
    """Turn NEEDS_CHOICE into one prepared category and the shared routing view."""

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

    select = next(
        child
        for child in view.children
        if isinstance(
            child,
            discord.ui.Select,
        )
    )
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

    assert isinstance(
        kwargs["view"],
        AdminRoutingSelectionView,
    )
    assert "Claviger Admin" in kwargs["content"]
