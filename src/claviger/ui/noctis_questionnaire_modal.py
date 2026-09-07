import discord

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.ui.catalog_selection_modal import (
    CatalogSelectionModal,
    CatalogSelectionOption,
)


class NoctisQuestionnaireModal(
    CatalogSelectionModal,
):
    """Configure a member's Noctis adult-access selection."""

    def __init__(
        self,
        *,
        coordinator: NoctisWorkflowCoordinatorService,
        policy: GuildPolicy,
        questionnaire: AdultAccessQuestionnaire,
        actor_id: int,
    ) -> None:
        self.coordinator = coordinator
        self.policy = policy
        self.questionnaire = questionnaire

        selected_keys = set(
            questionnaire.selected_theme_keys,
        )

        options = tuple(
            CatalogSelectionOption(
                key=theme.theme_key,
                label=theme.label,
                description=theme.description,
                emoji=theme.emoji,
                selected=(theme.theme_key in selected_keys),
            )
            for theme in questionnaire.themes
        )

        super().__init__(
            title="Configuration des accès Noctis",
            actor_id=actor_id,
            group_label="Accès souhaités",
            group_description=(
                "Sélectionnez les catégories auxquelles vous souhaitez accéder."
            ),
            options=options,
            checkbox_custom_id="noctis-themes",
        )

        self.ai_checkbox = discord.ui.Checkbox(
            custom_id="noctis-ai",
            default=questionnaire.include_ai,
        )

        self.add_item(
            discord.ui.Label(
                text="Contenus générés par IA",
                description=(
                    "Active également les variantes IA des catégories sélectionnées."
                ),
                component=self.ai_checkbox,
            )
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Apply the submitted Noctis selection."""

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        # Modal submissions have no originating message to update.
        # thinking=True creates an editable deferred response.
        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        await interaction.edit_original_response(
            content=(
                "⏳ **Mise à jour de vos accès Noctis...**\n\n"
                "Claviger applique votre sélection."
            ),
        )

        try:
            result = await self.coordinator.apply_selection(
                interaction.guild,
                interaction.user,
                self.policy,
                self.selected_keys,
                include_ai=self.ai_checkbox.value,
            )

        except Exception:
            await interaction.edit_original_response(
                content=(
                    "❌ **Impossible de mettre à jour vos accès "
                    "Noctis.**\n\n"
                    "Vous pouvez relancer `/noctis` pour réessayer. "
                    "Claviger recalculera les modifications depuis "
                    "votre état actuel."
                ),
            )
            return

        await interaction.edit_original_response(
            content=(
                "✅ **Vos accès Noctis ont été mis à jour.**\n\n"
                f"Modifications appliquées : {result.change_count}."
            ),
        )
