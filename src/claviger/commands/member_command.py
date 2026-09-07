import discord
from discord import app_commands

from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.services.member_workflow_coordinator_service import (
    MemberWorkflowCoordinatorService,
)
from claviger.ui.member_questionnaire_modal import (
    MemberQuestionnaireModal,
)


def create_member_command(
    policy_resolver: PolicyResolver,
    database_status_service: DatabaseStatusService,
    member_workflow_coordinator_service: MemberWorkflowCoordinatorService,
) -> app_commands.Command:
    """Create the public /membre command."""

    @app_commands.command(
        name="membre",
        description="Gère ton rôle membre et tes centres d'intérêt.",
    )
    async def member(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        try:
            database_status = await database_status_service.check()

        except Exception:
            await interaction.response.send_message(
                ("Le questionnaire membre est temporairement indisponible."),
                ephemeral=True,
            )
            return

        if database_status.state != DatabaseState.READY:
            await interaction.response.send_message(
                (
                    "Le questionnaire membre est indisponible tant que "
                    "la base de données de Claviger n'est pas prête."
                ),
                ephemeral=True,
            )
            return

        try:
            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

        except Exception:
            await interaction.response.send_message(
                (
                    "Impossible de charger la configuration du serveur. "
                    "Réessaie dans quelques instants."
                ),
                ephemeral=True,
            )
            return

        if not policy.role_management_enabled:
            await interaction.response.send_message(
                "La gestion des rôles membre est désactivée sur ce serveur.",
                ephemeral=True,
            )
            return

        channel_name = getattr(
            interaction.channel,
            "name",
            None,
        )

        if channel_name != policy.salutations_channel_name:
            await interaction.response.send_message(
                (
                    "Cette commande doit être utilisée dans "
                    f"`#{policy.salutations_channel_name}`."
                ),
                ephemeral=True,
            )
            return

        try:
            questionnaire = (
                await member_workflow_coordinator_service.build_questionnaire(
                    interaction.guild,
                    interaction.user,
                    policy,
                )
            )

            modal = MemberQuestionnaireModal(
                coordinator=member_workflow_coordinator_service,
                policy=policy,
                questionnaire=questionnaire,
                actor_id=interaction.user.id,
            )

        except Exception:
            await interaction.response.send_message(
                (
                    "Impossible de préparer le questionnaire membre. "
                    "Réessaie dans quelques instants."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(
            modal,
        )

    return member
