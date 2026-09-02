import discord
from discord import app_commands

from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)
from claviger.services.say import (
    SayService,
    SayStyle,
)


def create_say_command(
    authorization_service: AuthorizationService,
    say_service: SayService,
) -> app_commands.Command:
    """Create the say command."""

    @app_commands.command(
        name="say",
        description="Fait envoyer un message par Claviger dans le salon choisi.",
    )
    @app_commands.describe(
        salon="Salon dans lequel Claviger doit envoyer le message.",
        message="Message que Claviger doit envoyer.",
        style="Style du message. Embed par défaut.",
    )
    @app_commands.choices(
        style=[
            app_commands.Choice(
                name="Embed",
                value=SayStyle.EMBED.value,
            ),
            app_commands.Choice(
                name="Plain",
                value=SayStyle.PLAIN.value,
            ),
        ]
    )
    async def say(
        interaction: discord.Interaction,
        salon: discord.TextChannel,
        message: str,
        style: str = SayStyle.EMBED.value,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if not await authorization_service.is_allowed(
            interaction.user,
            interaction.guild,
            Capability.SAY,
        ):
            await interaction.response.send_message(
                "Vous n'êtes pas autorisé à utiliser cette commande.",
                ephemeral=True,
            )
            return

        if salon.guild.id != interaction.guild.id:
            await interaction.response.send_message(
                "Le salon sélectionné n'appartient pas à ce serveur.",
                ephemeral=True,
            )
            return

        say_style = SayStyle(style)

        if say_style is SayStyle.PLAIN and not await authorization_service.is_allowed(
            interaction.user,
            interaction.guild,
            Capability.SAY_PLAIN,
        ):
            await interaction.response.send_message(
                "Vous n'êtes pas autorisé à envoyer un message sans signature visuelle.",
                ephemeral=True,
            )
            return

        await say_service.send(
            salon,
            message,
            style=say_style,
            color=interaction.user.color,
        )

        await interaction.response.send_message(
            f"Message envoyé dans {salon.mention}.",
            ephemeral=True,
        )

    return say
