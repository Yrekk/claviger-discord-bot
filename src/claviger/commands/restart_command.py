from collections.abc import Awaitable, Callable

import discord
from discord import app_commands

from claviger.models.runtime_restart_model import RuntimeRestartRequest

RestartCallback = Callable[
    [RuntimeRestartRequest],
    Awaitable[None],
]


def create_restart_command(
    restart_callback: RestartCallback,
) -> app_commands.Command:
    """Create the application runtime restart command."""

    @app_commands.command(
        name="restart",
        description="Redémarre proprement l'application Discord.",
    )
    async def restart(
        interaction: discord.Interaction,
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

        await interaction.response.send_message(
            "Redémarrage de l'application en cours…",
            ephemeral=True,
        )

        restart_request = RuntimeRestartRequest(
            application_id=interaction.application_id,
            interaction_token=interaction.token,
        )

        await restart_callback(
            restart_request,
        )

    return restart
