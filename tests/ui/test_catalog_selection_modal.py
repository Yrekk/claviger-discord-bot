from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.ui.catalog_selection_modal import (
    CatalogSelectionModal,
    CatalogSelectionOption,
)


def create_interaction(
    *,
    user_id: int = 42,
) -> Mock:
    """Create a mocked modal interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id

    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


def create_modal() -> CatalogSelectionModal:
    """Create a generic catalog modal for tests."""

    return CatalogSelectionModal(
        title="Catalogue de test",
        actor_id=42,
        group_label="Options",
        group_description="Choisissez vos options.",
        options=(
            CatalogSelectionOption(
                key="alpha",
                label="Alpha",
                description="Première option.",
                emoji="🅰️",
                selected=True,
            ),
            CatalogSelectionOption(
                key="beta",
                label="Beta",
                description="Deuxième option.",
                selected=False,
            ),
        ),
        checkbox_custom_id="test-catalog",
    )


def test_catalog_selection_modal_builds_checkbox_options() -> None:
    """Build Discord checkbox options from generic catalog entries."""

    modal = create_modal()

    options = modal.selection_group.options

    assert len(options) == 2

    assert options[0].value == "alpha"
    assert options[0].label == "🅰️ Alpha"
    assert options[0].description == "Première option."
    assert options[0].default is True

    assert options[1].value == "beta"
    assert options[1].label == "Beta"
    assert options[1].description == "Deuxième option."
    assert options[1].default is False


@pytest.mark.asyncio
async def test_catalog_selection_modal_rejects_other_user() -> None:
    """Prevent another member from submitting the modal."""

    modal = create_modal()

    interaction = create_interaction(
        user_id=99,
    )

    allowed = await modal.interaction_check(
        interaction,
    )

    assert allowed is False

    interaction.response.send_message.assert_awaited_once_with(
        "Ce questionnaire appartient à un autre utilisateur.",
        ephemeral=True,
    )


def test_catalog_selection_modal_rejects_more_than_ten_options() -> None:
    """Respect Discord's ten-option CheckboxGroup limit."""

    options = tuple(
        CatalogSelectionOption(
            key=f"option-{index}",
            label=f"Option {index}",
        )
        for index in range(11)
    )

    with pytest.raises(
        ValueError,
        match="at most 10 options",
    ):
        CatalogSelectionModal(
            title="Catalogue de test",
            actor_id=42,
            group_label="Options",
            group_description="Choisissez vos options.",
            options=options,
            checkbox_custom_id="test-catalog",
        )
