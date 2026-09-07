import discord

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.member_workflow_coordinator_service import (
    MemberWorkflowCoordinatorService,
)
from claviger.ui.catalog_selection_modal import (
    CatalogSelectionModal,
    CatalogSelectionOption,
)


class MemberQuestionnaireModal(CatalogSelectionModal):
    """Let a member select the public interests they want to follow."""

    def __init__(
        self,
        *,
        coordinator: MemberWorkflowCoordinatorService,
        policy: GuildPolicy,
        questionnaire: MemberInterestQuestionnaire,
        actor_id: int,
    ) -> None:
        self.coordinator = coordinator
        self.policy = policy
        self.questionnaire = questionnaire

        selected_keys = set(
            questionnaire.selected_interest_keys,
        )

        options = tuple(
            CatalogSelectionOption(
                key=interest.catalog_key,
                label=interest.label or interest.catalog_key,
                description=interest.description,
                emoji=interest.emoji,
                selected=interest.catalog_key in selected_keys,
            )
            for interest in questionnaire.interests
        )

        super().__init__(
            title="Centres d'intérêt",
            actor_id=actor_id,
            group_label="Choisis tes centres d'intérêt",
            group_description=(
                "Tu peux modifier cette sélection plus tard en relançant /membre."
            ),
            options=options,
            checkbox_custom_id="member_interests",
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Apply the member's submitted interest selection."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "Ce questionnaire doit être utilisé sur un serveur.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        await interaction.edit_original_response(
            content="Mise à jour de tes rôles en cours…",
        )

        try:
            result = await self.coordinator.apply_selection(
                interaction.guild,
                interaction.user,
                self.policy,
                self.selected_keys,
            )

        except Exception:
            await interaction.edit_original_response(
                content=(
                    "Impossible de mettre à jour tes centres d'intérêt. "
                    "Tu peux relancer `/membre` et réessayer."
                ),
            )
            return

        if result.change_count == 0:
            message = "Tes centres d'intérêt sont déjà à jour."

        elif result.change_count == 1:
            message = "Tes centres d'intérêt ont été mis à jour (1 modification)."

        else:
            message = (
                "Tes centres d'intérêt ont été mis à jour "
                f"({result.change_count} modifications)."
            )

        await interaction.edit_original_response(
            content=message,
        )
