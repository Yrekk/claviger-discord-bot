import discord
from discord import app_commands


def create_say_command(
    channel_id: int,
) -> app_commands.Command:
    """Create the owner-only say command."""

    @app_commands.command(
        name="say",
        description="Fait envoyer un message par Claviger dans le salon Forum.",
    )
    @app_commands.describe(
        message="Message que Claviger doit envoyer.",
    )
    async def say(
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        channel = interaction.guild.get_channel(channel_id)

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Le salon Forum configuré est introuvable ou n'est pas un salon textuel.",
                ephemeral=True,
            )
            return

        await channel.send(message)

        await interaction.response.send_message(
            f"Message envoyé dans {channel.mention}.",
            ephemeral=True,
        )

    return say