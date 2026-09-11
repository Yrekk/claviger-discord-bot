from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.restart_command import create_restart_command
from claviger.models.runtime_restart_model import RuntimeRestartRequest


def create_interaction(
    *,
    owner_id: int = 42,
    user_id: int = 42,
    application_id: int = 789,
    interaction_token: str = "restart-token",
) -> Mock:
    """Create a mocked guild interaction for restart command tests."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.owner_id = owner_id

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id

    interaction.guild = guild
    interaction.user = user
    interaction.application_id = application_id
    interaction.token = interaction_token

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


@pytest.mark.asyncio
async def test_restart_rejects_interaction_outside_guild() -> None:
    """Reject restart requests outside a Discord guild."""

    restart_callback = AsyncMock()

    command = create_restart_command(
        restart_callback,
    )

    interaction = create_interaction()
    interaction.guild = None

    await command.callback(
        interaction,
    )

    restart_callback.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_restart_rejects_non_owner() -> None:
    """Restrict application restart to the guild owner."""

    restart_callback = AsyncMock()

    command = create_restart_command(
        restart_callback,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    restart_callback.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_restart_acknowledges_before_requesting_restart() -> None:
    """Acknowledge the interaction before shutting down the Discord client."""

    restart_callback = AsyncMock()

    command = create_restart_command(
        restart_callback,
    )

    interaction = create_interaction(
        application_id=789,
        interaction_token="restart-token",
    )

    await command.callback(
        interaction,
    )

    interaction.response.send_message.assert_awaited_once_with(
        "Redémarrage de l'application en cours…",
        ephemeral=True,
    )

    restart_callback.assert_awaited_once_with(
        RuntimeRestartRequest(
            application_id=789,
            interaction_token="restart-token",
        )
    )


def test_restart_command_metadata() -> None:
    """Expose restart under the application administrative namespace."""

    command = create_restart_command(
        AsyncMock(),
    )

    assert command.name == "restart"
    assert command.description == ("Redémarre proprement l'application Discord.")
