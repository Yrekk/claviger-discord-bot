import discord
from discord import app_commands

from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.service import ReportService
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.ui.noctis_questionnaire_modal import (
    NoctisQuestionnaireModal,
)


def create_noctis_admin_group(
    noctis_workflow_coordinator_service: NoctisWorkflowCoordinatorService,
    policy_resolver: PolicyResolver,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's Noctis administration command group."""

    noctis_group = app_commands.Group(
        name="noctis",
        description="Administration et prévisualisation du workflow Noctis.",
    )

    @noctis_group.command(
        name="preview",
        description="Teste le questionnaire Noctis sans modifier les rôles.",
    )
    async def noctis_preview(
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

        try:
            status = await database_status_service.check()

            if status.state != DatabaseState.READY:
                await interaction.response.send_message(
                    (
                        "La base de données doit être prête avant "
                        "de tester le questionnaire Noctis. "
                        "Vérifie `/claviger database status`."
                    ),
                    ephemeral=True,
                )
                return

            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

            questionnaire = (
                await noctis_workflow_coordinator_service.build_questionnaire(
                    interaction.guild,
                    interaction.user,
                    policy,
                )
            )

            if not questionnaire.themes:
                await interaction.response.send_message(
                    (
                        "Aucun thème Noctis disponible. "
                        "Vérifie le catalogue des accès adultes."
                    ),
                    ephemeral=True,
                )
                return

            modal = NoctisQuestionnaireModal(
                questionnaire=questionnaire,
                actor_id=interaction.user.id,
            )

            await interaction.response.send_modal(
                modal,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="noctis.preview.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la prévisualisation Noctis",
                    summary=("Claviger n'a pas pu construire le questionnaire Noctis."),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.response.send_message(
                "Impossible de construire le questionnaire Noctis.",
                ephemeral=True,
            )

    return noctis_group
