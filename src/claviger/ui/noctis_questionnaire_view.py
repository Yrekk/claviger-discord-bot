import discord

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import AdultAccessTheme
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)


def _truncate_description(
    description: str,
) -> str:
    """Fit a catalog description inside a Discord select option."""

    if len(description) <= 100:
        return description

    return f"{description[:97]}..."


class NoctisThemeSelect(discord.ui.Select):
    """Select the logical adult-access themes."""

    def __init__(
        self,
        *,
        owner_view: "NoctisQuestionnaireView",
        themes: tuple[AdultAccessTheme, ...],
    ) -> None:
        if len(themes) > 25:
            raise ValueError("Discord supports at most 25 themes in one select menu.")

        selected_keys = set(
            owner_view.selected_theme_keys,
        )

        options = [
            discord.SelectOption(
                label=theme.label,
                value=theme.theme_key,
                description=_truncate_description(
                    theme.description,
                ),
                emoji=theme.emoji,
                default=theme.theme_key in selected_keys,
            )
            for theme in themes
        ]

        super().__init__(
            placeholder="Choisissez vos accès Noctis",
            min_values=0,
            max_values=len(options),
            options=options,
        )

        self.owner_view = owner_view

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Update the pending theme selection."""

        if interaction.user.id != self.owner_view.actor_id:
            await interaction.response.send_message(
                "Ce questionnaire appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        self.owner_view.selected_theme_keys = tuple(
            self.values,
        )

        await interaction.response.edit_message(
            view=self.owner_view,
        )


class NoctisQuestionnaireView(discord.ui.View):
    """Interactive adult-access questionnaire."""

    def __init__(
        self,
        *,
        coordinator: NoctisWorkflowCoordinatorService,
        policy: GuildPolicy,
        questionnaire: AdultAccessQuestionnaire,
        actor_id: int,
        preview: bool = False,
    ) -> None:
        super().__init__(
            timeout=600,
        )

        self.coordinator = coordinator
        self.policy = policy
        self.questionnaire = questionnaire
        self.actor_id = actor_id
        self.preview = preview

        self.selected_theme_keys = tuple(
            questionnaire.selected_theme_keys,
        )
        self.include_ai = questionnaire.include_ai

        if questionnaire.themes:
            self.add_item(
                NoctisThemeSelect(
                    owner_view=self,
                    themes=questionnaire.themes,
                )
            )

        self._refresh_ai_button()

    def _refresh_ai_button(self) -> None:
        """Refresh the IA toggle label and style."""

        if self.include_ai:
            self.toggle_ai.label = "Contenus IA : activés"
            self.toggle_ai.style = discord.ButtonStyle.success
        else:
            self.toggle_ai.label = "Contenus IA : désactivés"
            self.toggle_ai.style = discord.ButtonStyle.secondary

    @discord.ui.button(
        label="Contenus IA : désactivés",
        style=discord.ButtonStyle.secondary,
    )
    async def toggle_ai(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Toggle the global IA preference."""

        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Ce questionnaire appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        self.include_ai = not self.include_ai
        self._refresh_ai_button()

        await interaction.response.edit_message(
            view=self,
        )

    @discord.ui.button(
        label="Valider mes accès",
        style=discord.ButtonStyle.primary,
    )
    async def validate(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Preview or apply the current questionnaire state."""

        if interaction.user.id != self.actor_id:
            await interaction.response.send_message(
                "Ce questionnaire appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        if self.preview:
            await interaction.response.send_message(
                self._format_preview(),
                ephemeral=True,
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        try:
            result = await self.coordinator.apply_selection(
                interaction.guild,
                interaction.user,
                self.policy,
                self.selected_theme_keys,
                include_ai=self.include_ai,
            )
        except Exception:
            await interaction.response.send_message(
                (
                    "Impossible de mettre à jour vos accès Noctis. "
                    "Aucun nouveau questionnaire n'a été ouvert."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            (
                "✅ Vos accès Noctis ont été mis à jour.\n"
                f"Modifications appliquées : {result.change_count}."
            ),
            ephemeral=True,
        )

    def _format_preview(self) -> str:
        """Format the questionnaire state without changing Discord."""

        themes_by_key = {theme.theme_key: theme for theme in self.questionnaire.themes}

        selected_labels = [
            themes_by_key[theme_key].label
            for theme_key in self.selected_theme_keys
            if theme_key in themes_by_key
        ]

        if selected_labels:
            themes_text = "\n".join(f"- {label}" for label in selected_labels)
        else:
            themes_text = "- Aucun"

        ai_text = "activés" if self.include_ai else "désactivés"

        return (
            "**Aperçu Noctis — aucune modification appliquée**\n\n"
            "**Thèmes sélectionnés**\n"
            f"{themes_text}\n\n"
            f"**Contenus IA : {ai_text}**"
        )
