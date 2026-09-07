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


def create_noctis_command(
    noctis_workflow_coordinator_service: NoctisWorkflowCoordinatorService,
    policy_resolver: PolicyResolver,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Command:
    """Create the public /noctis command."""

    @app_commands.command(
        name="noctis",
        description="Configure vos accès aux espaces réservés aux adultes.",
    )
    async def noctis(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        try:
            status = await database_status_service.check()

            if status.state != DatabaseState.READY:
                await interaction.response.send_message(
                    ("La configuration des accès est temporairement indisponible."),
                    ephemeral=True,
                )
                return

            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

            if not policy.role_management_enabled or not policy.adult_access_enabled:
                await interaction.response.send_message(
                    ("La gestion des accès adultes est désactivée sur ce serveur."),
                    ephemeral=True,
                )
                return

            channel_name = getattr(
                interaction.channel,
                "name",
                None,
            )

            if channel_name != policy.adult_rules_channel_name:
                await interaction.response.send_message(
                    (
                        "Cette commande doit être utilisée dans "
                        f"`#{policy.adult_rules_channel_name}` après "
                        "avoir pris connaissance des règles."
                    ),
                    ephemeral=True,
                )
                return

            questionnaire = (
                await noctis_workflow_coordinator_service.build_questionnaire(
                    interaction.guild,
                    interaction.user,
                    policy,
                )
            )

            if not questionnaire.themes:
                await interaction.response.send_message(
                    "Aucun accès adulte n'est actuellement disponible.",
                    ephemeral=True,
                )
                return

            modal = NoctisQuestionnaireModal(
                coordinator=noctis_workflow_coordinator_service,
                policy=policy,
                questionnaire=questionnaire,
                actor_id=interaction.user.id,
            )

            await interaction.response.send_modal(
                modal,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="noctis.open.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de l'ouverture du questionnaire Noctis",
                    summary=(
                        "Claviger n'a pas pu ouvrir le questionnaire d'accès adulte."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.response.send_message(
                (
                    "Impossible d'ouvrir le questionnaire Noctis. "
                    "L'incident a été signalé."
                ),
                ephemeral=True,
            )

    return noctis
