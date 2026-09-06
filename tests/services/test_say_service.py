from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.say import SayService, SayStyle


def create_channel() -> Mock:
    """Create a mocked Discord text channel."""
    channel = Mock(spec=discord.TextChannel)
    channel.send = AsyncMock()

    return channel


@pytest.mark.asyncio
async def test_send_embed_message() -> None:
    """Send an embed using the requested message and color."""
    service = SayService()

    channel = create_channel()
    color = discord.Color(0xAABBCC)

    await service.send(
        channel,
        "Ave Claviger",
        style=SayStyle.EMBED,
        color=color,
    )

    channel.send.assert_awaited_once()

    embed = channel.send.await_args.kwargs["embed"]

    assert isinstance(embed, discord.Embed)
    assert embed.description == "Ave Claviger"
    assert embed.color == color


@pytest.mark.asyncio
async def test_send_plain_message() -> None:
    """Send the message directly when plain style is requested."""
    service = SayService()

    channel = create_channel()

    await service.send(
        channel,
        "Ave Claviger",
        style=SayStyle.PLAIN,
        color=discord.Color.default(),
    )

    channel.send.assert_awaited_once_with(
        "Ave Claviger",
    )
