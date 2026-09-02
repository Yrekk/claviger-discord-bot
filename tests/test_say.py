from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.say import create_say_command
from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)
from claviger.services.say import (
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

    return channel


@pytest.fixture
def authorization_service() -> Mock:
    """Create a mocked authorization service allowed by default."""
    service = Mock(spec=AuthorizationService)
    service.is_allowed = AsyncMock(return_value=True)

    return service


@pytest.fixture
def say_service() -> Mock:
    """Create a mocked say service."""
    service = Mock(spec=SayService)
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
    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
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

    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Vous n'êtes pas autorisé à utiliser cette commande.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_uses_embed_style_by_default(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Use the embed style when no explicit style is requested."""
    command = create_say_command(
        authorization_service,
        say_service,
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

    say_service.send.assert_awaited_once_with(
        channel,
        "Ave Claviger",
        style=SayStyle.EMBED,
        color=interaction.user.color,
    )

    interaction.response.send_message.assert_awaited_once_with(
        "Message envoyé dans #forum.",
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
    )

    interaction = create_interaction()

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
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
        channel,
        "Ave Claviger",
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
    )

    interaction = create_interaction()

    channel = create_text_channel(
        guild=interaction.guild,
    )

    await command.callback(
        interaction,
        channel,
        "Ave Claviger",
        SayStyle.PLAIN.value,
    )

    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Vous n'êtes pas autorisé à envoyer un message sans signature visuelle.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_say_rejects_channel_from_another_guild(
    authorization_service: Mock,
    say_service: Mock,
) -> None:
    """Reject a text channel that belongs to another Discord server."""
    command = create_say_command(
        authorization_service,
        say_service,
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

    say_service.send.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Le salon sélectionné n'appartient pas à ce serveur.",
        ephemeral=True,
    )
