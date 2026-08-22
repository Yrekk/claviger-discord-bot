import discord
from discord import app_commands


def create_say_command() -> app_commands.Command:
    """Create the owner-only say command."""

    @app_commands.command(
        name="say",
        description="Fait envoyer un message par Claviger dans le salon choisi.",
    )
    @app_commands.describe(
        salon="Salon dans lequel Claviger doit envoyer le message.",
        message="Message que Claviger doit envoyer.",
    )
    async def say(
        interaction: discord.Interaction,
        salon: discord.TextChannel,
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

        if salon.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                "Le salon sélectionné n'appartient pas à ce serveur.",
                ephemeral=True,
            )
            return

        await salon.send(message)

        await interaction.response.send_message(
            f"Message envoyé dans {salon.mention}.",
            ephemeral=True,
        )

    return say