import discord
from discord import app_commands

from claviger.database.status import DatabaseState
from claviger.reporting.service import ReportService
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationCoordinatorService,
)
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)
from claviger.ui.admin.admin_configuration_view import (
    run_admin_configuration,
)
from claviger.ui.admin.guild_ai_configuration_view import (
    run_guild_ai_configuration,
)
from claviger.ui.workflows.workflow_configuration_view import (
    run_workflow_configuration,
)


def create_config_server_command(
    admin_coordinator: AdminConfigurationCoordinatorService,
    ai_configuration_coordinator: GuildAIConfigurationCoordinatorService,
    workflow_coordinator: WorkflowConfigurationCoordinatorService,
    *,
    admin_command_name: str,
    database_state: DatabaseState,
    database_ownership_bound: bool,
    report_service: ReportService | None = None,
) -> app_commands.Command:
    """Create the complete guild configuration command."""

    @app_commands.command(
        name="config-server",
        description="Configure l'administration et les workflows du serveur.",
    )
    async def config_server(
        interaction: discord.Interaction,
    ) -> None:
        """Run server configuration from ADMIN through AI into workflow setup."""

        # Server configuration is always guild-scoped. DM execution must never
        # attempt to infer or reuse a Discord guild from another runtime state.
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        # Structural configuration can create channels, categories and roles.
        # Only the Discord guild owner may initiate that workflow.
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        # Guild configuration is meaningful only after the shared application
        # database has reached the current schema version.
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

        # A READY schema still remains unusable until ownership has explicitly
        # been bound to the authenticated Discord application.
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

        # ADMIN remains the operational prerequisite because reporting,
        # command routing and later diagnostics depend on its destinations.
        admin_ready = await run_admin_configuration(
            interaction,
            coordinator=admin_coordinator,
            admin_command_name=admin_command_name,
            report_service=report_service,
            continue_configuration=True,
        )

        if not admin_ready:
            # IMPORT, NEEDS_CHOICE and incomplete COMPLETE paths already expose
            # their own interactive ADMIN continuation. Later stages must not
            # start until that routing has actually been persisted.
            return

        async def continue_workflow_configuration(
            source_interaction: discord.Interaction,
        ) -> None:
            """Open workflow setup after the shared guild AI stage is ready."""

            await run_workflow_configuration(
                source_interaction,
                coordinator=workflow_coordinator,
                admin_command_name=admin_command_name,
                report_service=report_service,
            )

        # The Discord command does not interpret AI states itself. The dedicated
        # backend coordinator and UI adapter decide whether the guild may proceed
        # immediately or must collect/repair the shared AI configuration first.
        ai_ready = await run_guild_ai_configuration(
            interaction,
            coordinator=ai_configuration_coordinator,
            continuation=continue_workflow_configuration,
        )

        if not ai_ready:
            return

        await continue_workflow_configuration(
            interaction,
        )

    return config_server
