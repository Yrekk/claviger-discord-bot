from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.say import create_say_command


def create_interaction(
    *,
    guild_id: int = 123,
    owner_id: int = 42,
    user_id: int = 42,
) -> Mock:
    """Create a mocked Discord interaction for say command tests."""
    interaction = Mock(spec=discord.Interaction)

    guild = Mock(spec=discord.Guild)
    guild.id = guild_id
    guild.owner_id = owner_id

    user = Mock(spec=discord.Member)
    user.id = user_id

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


@pytest.mark.asyncio
async def test_say_rejects_interaction_outside_guild() -> None:
    """Reject the say command when it is used outside a Discord server."""
    command = create_say_command()

    interaction = create_interaction()
    interaction.guild = None

    channel = Mock(spec=discord.TextChannel)

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_non_owner() -> None:
    """Reject the say command when the user is not the server owner."""
    command = create_say_command()

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    channel.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_sends_message_to_selected_channel() -> None:
    """Send the requested message to the selected text channel."""
    command = create_say_command()

    interaction = create_interaction()

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
    )

    channel.send.assert_awaited_once_with(
        "Ave Claviger",
    )

    interaction.response.send_message.assert_awaited_once_with(
        "Message envoyé dans #forum.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_channel_from_another_guild() -> None:
    """Reject a text channel that belongs to another Discord server."""
    command = create_say_command()

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

    channel.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Le salon sélectionné n'appartient pas à ce serveur.",
        ephemeral=True,
    )