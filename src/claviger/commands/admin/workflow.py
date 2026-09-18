import discord
from discord import app_commands

from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)
from claviger.ui.workflows.workflow_ai_questionnaire_owner_view import (
    WorkflowAIQuestionnaireOwnerCurrentView,
    WorkflowAIQuestionnaireOwnerSelectionView,
)


def create_workflow_group(
    owner_service: GuildAIQuestionnaireOwnerService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create owner-only workflow administration commands."""

    workflow_group = app_commands.Group(
        name="workflow",
        description="Configure les workflows génériques du serveur.",
    )

    @workflow_group.command(
        name="ai-questionnaire",
        description="Choisit le workflow qui demande la préférence IA.",
    )
    async def configure_ai_questionnaire(
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

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            inspection = await owner_service.inspect(
                interaction.guild.id,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="workflow.ai_questionnaire.inspect_failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la configuration du questionnaire IA",
                    summary=(
                        "Claviger n'a pas pu inspecter les workflows disponibles."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Impossible d'inspecter les workflows configurés.",
                ephemeral=True,
            )
            return

        if not inspection.can_assign_owner:
            await interaction.followup.send(
                (
                    "L'IA doit d'abord être activée et disposer d'un rôle global. "
                    "Relance config-server, active l'IA et configure son rôle."
                ),
                ephemeral=True,
            )
            return

        if not inspection.workflows:
            await interaction.followup.send(
                (
                    "Aucun workflow actif n'est disponible. "
                    "Crée d'abord un workflow avec config-server."
                ),
                ephemeral=True,
            )
            return

        owner_key = inspection.owner_workflow_key
        workflows_by_key = {
            workflow.workflow_key: workflow
            for workflow in inspection.workflows
        }

        if owner_key is None:
            await interaction.followup.send(
                (
                    "**Questionnaire de préférence IA**\n\n"
                    "Aucun workflow ne pose encore la question IA. "
                    "Choisis celui qui en deviendra l'unique propriétaire."
                ),
                ephemeral=True,
                view=WorkflowAIQuestionnaireOwnerSelectionView(
                    owner_service=owner_service,
                    report_service=report_service,
                    workflows=inspection.workflows,
                    actor_id=interaction.user.id,
                    guild_id=interaction.guild.id,
                    current_owner_key=None,
                ),
            )
            return

        owner = workflows_by_key.get(
            owner_key,
        )

        owner_label = (
            f"/{owner.command_name}"
            if owner is not None
            else owner_key
        )

        await interaction.followup.send(
            (
                "**Questionnaire de préférence IA**\n\n"
                f"Le workflow {owner_label} est actuellement le seul "
                "autorisé à proposer l'option IA.\n\n"
                "Veux-tu déplacer cette question vers un autre workflow ?"
            ),
            ephemeral=True,
            view=WorkflowAIQuestionnaireOwnerCurrentView(
                owner_service=owner_service,
                report_service=report_service,
                workflows=inspection.workflows,
                actor_id=interaction.user.id,
                guild_id=interaction.guild.id,
                current_owner_key=owner_key,
            ),
        )

    return workflow_group
