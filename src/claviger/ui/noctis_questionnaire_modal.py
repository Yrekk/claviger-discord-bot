import discord

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.ui.catalog_selection_modal import (
    CatalogSelectionModal,
    CatalogSelectionOption,
)


class NoctisQuestionnaireModal(
    CatalogSelectionModal,
):
    """Noctis questionnaire using the generic catalog selection modal."""

    def __init__(
        self,
        *,
        questionnaire: AdultAccessQuestionnaire,
        actor_id: int,
    ) -> None:
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
        """Display the preview result without modifying roles."""

        themes_by_key = {theme.theme_key: theme for theme in self.questionnaire.themes}

        selected_labels = [
            themes_by_key[theme_key].label
            for theme_key in self.selected_keys
            if theme_key in themes_by_key
        ]

        if selected_labels:
            themes_text = "\n".join(f"- {label}" for label in selected_labels)
        else:
            themes_text = "- Aucun"

        ai_text = "activés" if self.ai_checkbox.value else "désactivés"

        await interaction.response.send_message(
            (
                "✅ **Aperçu Noctis — aucune modification appliquée**\n\n"
                "**Accès sélectionnés**\n"
                f"{themes_text}\n\n"
                f"**Contenus IA : {ai_text}**"
            ),
            ephemeral=True,
        )
