from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.say import create_say_command
from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)


# Helper functions to create mocked Discord objects for say command tests.


def create_interaction(
    *,
    guild_id: int = 123,
    user_id: int = 42,
    user_color: int = 0x5865F2,
) -> Mock:
    """Create a mocked Discord interaction for say command tests."""
    interaction = Mock(spec=discord.Interaction)

    guild = Mock(spec=discord.Guild)
    guild.id = guild_id

    user = Mock(spec=discord.Member)
    user.id = user_id
    user.color = discord.Color(user_color)

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


def create_text_channel(
    *,
    guild: discord.Guild,
) -> Mock:
    """Create a mocked Discord text channel."""
    channel = Mock(spec=discord.TextChannel)

    channel.guild = guild
    channel.mention = "#forum"
    channel.send = AsyncMock()

    return channel


@pytest.fixture
def authorization_service() -> Mock:
    """Create a mocked authorization service allowed by default."""
    service = Mock(spec=AuthorizationService)
    service.is_allowed = AsyncMock(return_value=True)

    return service


# Tests for the say command.


@pytest.mark.asyncio
async def test_say_rejects_interaction_outside_guild(
    authorization_service: Mock,
) -> None:
    """Reject the say command when it is used outside a Discord server."""
    command = create_say_command(
        authorization_service,
    )

    interaction = create_interaction()
    interaction.guild = None

    channel = Mock(spec=discord.TextChannel)

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    authorization_service.is_allowed.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_unauthorized_user(
    authorization_service: Mock,
) -> None:
    """Reject the say command when authorization is denied."""
    authorization_service.is_allowed.return_value = False

    command = create_say_command(
        authorization_service,
    )

    interaction = create_interaction()

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    authorization_service.is_allowed.assert_awaited_once_with(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    channel.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Vous n'êtes pas autorisé à utiliser cette commande.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_sends_message_to_selected_channel(
    authorization_service: Mock,
) -> None:
    """Send the requested message to the selected text channel."""
    command = create_say_command(
        authorization_service,
    )

    interaction = create_interaction()

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    authorization_service.is_allowed.assert_awaited_once_with(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    channel.send.assert_awaited_once()

    call = channel.send.await_args

    embed = call.kwargs["embed"]

    assert isinstance(embed, discord.Embed)
    assert embed.description == "Ave Claviger"
    assert embed.color == interaction.user.color

    interaction.response.send_message.assert_awaited_once_with(
        "Message envoyé dans #forum.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_channel_from_another_guild(
    authorization_service: Mock,
) -> None:
    """Reject a text channel that belongs to another Discord server."""
    command = create_say_command(
        authorization_service,
    )

    interaction = create_interaction(
        guild_id=123,
    )

    other_guild = Mock(spec=discord.Guild)
    other_guild.id = 456

    channel = create_text_channel(
        guild=other_guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    authorization_service.is_allowed.assert_awaited_once_with(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    channel.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Le salon sélectionné n'appartient pas à ce serveur.",
        ephemeral=True,
    )