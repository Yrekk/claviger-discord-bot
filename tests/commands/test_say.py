from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.say_command import create_say_command
from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)
from claviger.services.say_service import (
    SayService,
    SayStyle,
)


def create_interaction(
    *,
    guild_id: int = 123,
    user_id: int = 42,
    user_color: int = 0x5865F2,
) -> Mock:
    """Create a mocked Discord interaction for say command tests."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = guild_id

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id
    user.color = discord.Color(
        user_color,
    )

    channel = Mock(
        spec=discord.TextChannel,
    )
    channel.guild = guild
    channel.mention = "#general"

    interaction.guild = guild
    interaction.user = user
    interaction.channel = channel

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


@pytest.fixture
def authorization_service() -> Mock:
    """Create a mocked authorization service allowed by default."""

    service = Mock(
        spec=AuthorizationService,
    )
    service.is_allowed = AsyncMock(
        return_value=True,
    )

    return service


@pytest.fixture
def say_service() -> Mock:
    """Create a mocked say service."""

    service = Mock(
        spec=SayService,
    )
    service.send = AsyncMock()

    return service


@pytest.mark.asyncio
async def test_say_rejects_interaction_outside_guild(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Reject the say command when it is used outside a Discord server."""

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()
    interaction.guild = None

    await command.callback(
        interaction,
        "Test message",
    )

    authorization_service.is_allowed.assert_not_awaited()
    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_non_text_channel(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Reject the say command outside a supported text channel."""

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()
    interaction.channel = Mock(
        spec=discord.VoiceChannel,
    )

    await command.callback(
        interaction,
        "Test message",
    )

    authorization_service.is_allowed.assert_not_awaited()
    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée dans un salon textuel.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_unauthorized_user(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Reject the say command when authorization is denied."""

    authorization_service.is_allowed.return_value = False

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
        "Test message",
    )

    authorization_service.is_allowed.assert_awaited_once_with(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Vous n'êtes pas autorisé à utiliser cette commande.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_uses_current_channel_with_embed_style_by_default(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Send the default embed message in the current interaction channel."""

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
        "Test message",
    )

    authorization_service.is_allowed.assert_awaited_once_with(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    say_service.send.assert_awaited_once_with(
        interaction.channel,
        "Test message",
        style=SayStyle.EMBED,
        color=interaction.user.color,
    )

    interaction.response.send_message.assert_awaited_once_with(
        "Message envoyé dans #general.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_allows_plain_style_with_permission(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Allow plain messages when the user has the plain say capability."""

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
        "Test message",
        SayStyle.PLAIN.value,
    )

    assert authorization_service.is_allowed.await_count == 2

    authorization_service.is_allowed.assert_any_await(
        interaction.user,
        interaction.guild,
        Capability.SAY,
    )

    authorization_service.is_allowed.assert_any_await(
        interaction.user,
        interaction.guild,
        Capability.SAY_PLAIN,
    )

    say_service.send.assert_awaited_once_with(
        interaction.channel,
        "Test message",
        style=SayStyle.PLAIN,
        color=interaction.user.color,
    )


@pytest.mark.asyncio
async def test_say_rejects_plain_style_without_permission(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Reject plain messages when the user lacks the plain say capability."""

    authorization_service.is_allowed.side_effect = [
        True,
        False,
    ]

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
        "Test message",
        SayStyle.PLAIN.value,
    )

    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        ("Vous n'êtes pas autorisé à envoyer un message sans signature visuelle."),
        ephemeral=True,
    )


def test_say_uses_bot_display_name_in_discord_metadata(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Expose the guild bot display name in the say command metadata."""

    command = create_say_command(
        authorization_service,
        say_service,
        bot_display_name="Vespera",
    )

    assert command.name == "say"
    assert command.description == (
        "Fait envoyer un message par Vespera dans le salon actuel."
    )

    message_parameter = next(
        parameter for parameter in command.parameters if parameter.name == "message"
    )

    assert message_parameter.description == "Message que Vespera doit envoyer."
