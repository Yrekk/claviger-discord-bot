from enum import StrEnum

import discord


class SayStyle(StrEnum):
    """Available rendering styles for messages sent through /say."""

    EMBED = "embed"
    PLAIN = "plain"


class SayService:
    """Send messages through Claviger using the requested rendering style."""

    async def send(
        self,
        channel: discord.TextChannel,
        message: str,
        *,
        style: SayStyle,
        color: discord.Color,
    ) -> None:
        """Send a message using the requested style."""

        if style is SayStyle.PLAIN:
            await channel.send(message)
            return

        embed = discord.Embed(
            description=message,
            color=color,
        )

        await channel.send(
            embed=embed,
        )