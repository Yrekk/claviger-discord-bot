import logging

import discord
from discord import app_commands

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfigurationInspectionState,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.workflows.workflow_questionnaire_coordinator_service import (
    WorkflowQuestionnaireAIUnavailableError,
    WorkflowQuestionnaireCoordinatorService,
)
from claviger.ui.workflows.workflow_questionnaire_view import (
    WorkflowQuestionnaireUIError,
    open_workflow_questionnaire,
)

logger = logging.getLogger(__name__)


def create_generic_workflow_command(
    *,
    workflow: WorkflowDefinition,
    coordinator: WorkflowQuestionnaireCoordinatorService,
    report_service: ReportService | None,
) -> app_commands.Command:
    """Create one slash command from a persisted workflow definition."""

    @app_commands.command(
        name=workflow.command_name,
        description=workflow.command_description,
    )
    async def generic_workflow(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None or not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if (
            workflow.channel_mode == "restricted"
            and interaction.channel_id not in workflow.channel_ids
        ):
            destinations = " ".join(
                f"<#{channel_id}>"
                for channel_id in workflow.channel_ids
            )
            destinations = (
                destinations
                or "les salons configurés pour ce workflow"
            )

            await interaction.response.send_message(
                f"Cette commande doit être utilisée dans {destinations}.",
                ephemeral=True,
            )
            return

        try:
            questionnaire = await coordinator.build_questionnaire(
                guild=interaction.guild,
                member=interaction.user,
                workflow_key=workflow.workflow_key,
            )

            await open_workflow_questionnaire(
                interaction,
                coordinator=coordinator,
                questionnaire=questionnaire,
                report_service=report_service,
            )
        except WorkflowQuestionnaireAIUnavailableError as error:
            logger.error(
                "AI configuration drift blocks workflow %s on guild %s: %s.",
                workflow.workflow_key,
                interaction.guild.id,
                error.state.value,
            )

            if error.state is GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND:
                title = "Rôle IA configuré introuvable"
                summary = (
                    "Le rôle IA global configuré n'existe plus sur Discord. "
                    "Les questionnaires sont bloqués pour éviter de confondre "
                    "ce drift avec une préférence IA désactivée."
                )
                action = (
                    "Recréer ou réaffecter le rôle IA depuis l'administration "
                    "Claviger avant de relancer les questionnaires."
                )
            else:
                title = "Configuration IA live indisponible"
                summary = (
                    "La configuration IA persistée ne peut pas être utilisée "
                    "en sécurité dans l'état Discord actuel."
                )
                action = (
                    "Contrôler la configuration IA et la ressource Discord "
                    "associée avant de relancer les questionnaires."
                )

            if report_service is not None:
                await report_service.emit(
                    ReportEvent(
                        event_type="workflow.ai_configuration_drift",
                        severity=ReportSeverity.ERROR,
                        title=title,
                        summary=summary,
                        details=(
                            f"state={error.state.value}\n"
                            f"ai_role_id={error.ai_role_id}\n"
                            f"action={action}"
                        ),
                        guild_id=interaction.guild.id,
                        guild_label=interaction.guild.name,
                        actor_id=interaction.user.id,
                        actor_label=interaction.user.display_name,
                    )
                )

            await interaction.response.send_message(
                (
                    "❌ La configuration IA du serveur est actuellement "
                    "indisponible. L'administrateur a été prévenu."
                ),
                ephemeral=True,
            )
        except WorkflowQuestionnaireUIError as error:
            await interaction.response.send_message(
                (
                    "Ce questionnaire dépasse actuellement les limites "
                    f"de l'interface Discord : {error}"
                ),
                ephemeral=True,
            )
        except Exception as error:
            logger.exception(
                "Unable to prepare workflow %s for guild %s.",
                workflow.workflow_key,
                interaction.guild.id,
            )

            if report_service is not None:
                await report_service.emit(
                    ReportEvent(
                        event_type="workflow.questionnaire.prepare_failed",
                        severity=ReportSeverity.ERROR,
                        title="Échec de préparation du questionnaire",
                        summary=(
                            f"Le workflow /{workflow.command_name} "
                            "n'a pas pu préparer son questionnaire."
                        ),
                        details=f"{type(error).__name__}: {error}",
                        guild_id=interaction.guild.id,
                        guild_label=interaction.guild.name,
                        actor_id=interaction.user.id,
                        actor_label=interaction.user.display_name,
                    )
                )

            await interaction.response.send_message(
                (
                    "❌ Impossible de préparer ce questionnaire. "
                    "L'incident a été signalé."
                ),
                ephemeral=True,
            )

    return generic_workflow
