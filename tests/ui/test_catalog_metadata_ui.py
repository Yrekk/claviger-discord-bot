from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.catalog_next_selection_model import (
    CatalogNextSelection,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.ui.catalog_metadata_modal import (
    CatalogMetadataModal,
)
from claviger.ui.catalog_next_view import CatalogNextView


def create_entry(
    *,
    role_id: int,
    role_name: str,
    catalog_key: str,
) -> RoleChannelCatalogEntry:
    """Create one technically valid catalog entry."""

    return RoleChannelCatalogEntry(
        guild_id=123,
        role_id=role_id,
        role_name=role_name,
        catalog_key=catalog_key,
        channel_id=200,
        channel_name="channel",
        label=None,
        description=None,
        emoji=None,
        sort_order=10,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


def create_selection(
    *,
    role_id: int = 100,
    role_name: str = "interest-ludus",
    catalog_key: str = "ludus",
) -> CatalogNextSelection:
    """Create one catalog selection."""

    return CatalogNextSelection(
        catalog_key="member_interests",
        display_name="Member interests",
        entry_name="Member interest",
        entry=create_entry(
            role_id=role_id,
            role_name=role_name,
            catalog_key=catalog_key,
        ),
    )


def create_interaction(
    *,
    user_id: int = 42,
) -> Mock:
    """Create a mocked Discord component interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    return interaction


@pytest.mark.asyncio
async def test_modal_updates_metadata_and_offers_next() -> None:
    """Persist metadata and expose the next button when work remains."""

    coordinator = Mock(
        spec=CatalogNextCoordinatorService,
    )
    coordinator.update_metadata = AsyncMock()
    coordinator.get_next = AsyncMock(
        return_value=create_selection(
            role_id=101,
            role_name="interest-musicae",
            catalog_key="musicae",
        ),
    )

    selection = create_selection()

    modal = CatalogMetadataModal(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        selection=selection,
        actor_id=42,
    )

    modal.label_input._value = "Jeux vidéo"
    modal.description_input._value = "Discussions autour du jeu vidéo."
    modal.emoji_input._value = "🎮"

    interaction = create_interaction()

    await modal.on_submit(
        interaction,
    )

    coordinator.update_metadata.assert_awaited_once_with(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
        "member_interests",
        100,
        label="Jeux vidéo",
        description="Discussions autour du jeu vidéo.",
        emoji="🎮",
    )

    coordinator.get_next.assert_awaited_once_with(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    kwargs = interaction.response.send_message.await_args.kwargs

    assert isinstance(
        kwargs["view"],
        CatalogNextView,
    )


@pytest.mark.asyncio
async def test_modal_finishes_when_every_catalog_is_complete() -> None:
    """Finish the workflow when no incomplete entry remains."""

    coordinator = Mock(
        spec=CatalogNextCoordinatorService,
    )
    coordinator.update_metadata = AsyncMock()
    coordinator.get_next = AsyncMock(
        return_value=None,
    )

    modal = CatalogMetadataModal(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        selection=create_selection(),
        actor_id=42,
    )

    modal.label_input._value = "Jeux vidéo"
    modal.description_input._value = "Discussions autour du jeu vidéo."
    modal.emoji_input._value = ""

    interaction = create_interaction()

    await modal.on_submit(
        interaction,
    )

    message = interaction.response.send_message.await_args.args[0]

    assert "Tous les catalogues disponibles sont configurés" in message

    kwargs = interaction.response.send_message.await_args.kwargs

    assert "view" not in kwargs


@pytest.mark.asyncio
async def test_next_view_opens_modal_for_next_entry() -> None:
    """Open a fresh metadata modal from the next button."""

    coordinator = Mock(
        spec=CatalogNextCoordinatorService,
    )
    coordinator.get_next = AsyncMock(
        return_value=create_selection(),
    )

    view = CatalogNextView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        actor_id=42,
    )

    interaction = create_interaction()

    button = view.children[0]

    await button.callback(
        interaction,
    )

    coordinator.get_next.assert_awaited_once_with(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    modal = interaction.response.send_modal.await_args.args[0]

    assert isinstance(
        modal,
        CatalogMetadataModal,
    )


@pytest.mark.asyncio
async def test_next_view_rejects_other_user() -> None:
    """Prevent another user from consuming someone else's workflow."""

    coordinator = Mock(
        spec=CatalogNextCoordinatorService,
    )
    coordinator.get_next = AsyncMock()

    view = CatalogNextView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        actor_id=42,
    )

    interaction = create_interaction(
        user_id=99,
    )

    button = view.children[0]

    await button.callback(
        interaction,
    )

    coordinator.get_next.assert_not_awaited()
    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()
