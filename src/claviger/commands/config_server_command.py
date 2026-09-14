import discord
from discord import app_commands

from claviger.database.status import DatabaseState
from claviger.reporting.service import ReportService
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.ui.admin_configuration_view import run_admin_configuration


def create_config_server_command(
    coordinator: AdminConfigurationCoordinatorService,
    *,
    admin_command_name: str,
    database_state: DatabaseState,
    database_ownership_bound: bool,
    report_service: ReportService | None = None,
) -> app_commands.Command:
    """Create the guild ADMIN configuration command."""

    @app_commands.command(
        name="config-server",
        description="Configure la structure d'administration du serveur.",
    )
    async def config_server(
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

        if database_state != DatabaseState.READY:
            await interaction.response.send_message(
                (
                    "La configuration du serveur est indisponible tant que "
                    "la base de données n'est pas prête. "
                    f"Utilise `/{admin_command_name} database status` "
                    "pour connaître l'action nécessaire."
                ),
                ephemeral=True,
            )
            return

        if not database_ownership_bound:
            await interaction.response.send_message(
                (
                    "La base de données est prête mais n'est pas encore liée "
                    "à cette application. "
                    f"Utilise `/{admin_command_name} database bind`, puis "
                    f"`/{admin_command_name} restart` avant de configurer "
                    "le serveur."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        await run_admin_configuration(
            interaction,
            coordinator=coordinator,
            admin_command_name=admin_command_name,
            report_service=report_service,
        )

    return config_server
