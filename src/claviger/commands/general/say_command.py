import discord
from discord import app_commands

from claviger.services.authorization import (
    AuthorizationService,
    Capability,
)
from claviger.services.say_service import (
    SayService,
    SayStyle,
)


def create_say_command(
    authorization_service: AuthorizationService,
    say_service: SayService,
    *,
    bot_display_name: str,
) -> app_commands.Command:
    """Create the say command."""

    @app_commands.command(
        name="say",
        description=(
            f"Fait envoyer un message par {bot_display_name} dans le salon actuel."
        ),
    )
    @app_commands.describe(
        message=f"Message que {bot_display_name} doit envoyer.",
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
        message: str,
        style: str = SayStyle.EMBED.value,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        channel = interaction.channel

        if not isinstance(
            channel,
            discord.TextChannel,
        ):
            await interaction.response.send_message(
                "Cette commande doit être utilisée dans un salon textuel.",
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

        say_style = SayStyle(style)

        if say_style is SayStyle.PLAIN and not await authorization_service.is_allowed(
            interaction.user,
            interaction.guild,
            Capability.SAY_PLAIN,
        ):
            await interaction.response.send_message(
                (
                    "Vous n'êtes pas autorisé à envoyer un message "
                    "sans signature visuelle."
                ),
                ephemeral=True,
            )
            return

        await say_service.send(
            channel,
            message,
            style=say_style,
            color=interaction.user.color,
        )

        await interaction.response.send_message(
            f"Message envoyé dans {channel.mention}.",
            ephemeral=True,
        )

    return say
