import discord

from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import AdultAccessTheme
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)

MAX_THEME_BUTTONS = 20
THEME_BUTTONS_PER_ROW = 5


def _build_theme_button_label(
    theme: AdultAccessTheme,
    *,
    selected: bool,
) -> str:
    """Build a checkbox-like Discord button label."""

    checkbox = "☑" if selected else "☐"

    emoji = f"{theme.emoji} " if theme.emoji else ""

    label = f"{checkbox} {emoji}{theme.label}"

    # Discord button labels are limited to 80 characters.
    return label[:80]


class NoctisThemeButton(discord.ui.Button):
    """Toggle one logical Noctis access theme."""

    def __init__(
        self,
        *,
        owner_view: "NoctisQuestionnaireView",
        theme: AdultAccessTheme,
        row: int,
    ) -> None:
        self.owner_view = owner_view
        self.theme = theme

        selected = theme.theme_key in owner_view.selected_theme_keys

        super().__init__(
            label=_build_theme_button_label(
                theme,
                selected=selected,
            ),
            style=(
                discord.ButtonStyle.success
                if selected
                else discord.ButtonStyle.secondary
            ),
            custom_id=f"noctis-theme:{theme.theme_key}",
            row=row,
        )

    def refresh_from_view(self) -> None:
        """Refresh visual state from the questionnaire."""

        selected = self.theme.theme_key in self.owner_view.selected_theme_keys

        self.label = _build_theme_button_label(
            self.theme,
            selected=selected,
        )

        self.style = (
            discord.ButtonStyle.success if selected else discord.ButtonStyle.secondary
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Toggle this theme in the pending selection."""

        if interaction.user.id != self.owner_view.actor_id:
            await interaction.response.send_message(
                "Ce questionnaire appartient à un autre utilisateur.",
                ephemeral=True,
            )
            return

        selected_keys = set(
            self.owner_view.selected_theme_keys,
        )

        if self.theme.theme_key in selected_keys:
            selected_keys.remove(
                self.theme.theme_key,
            )
        else:
            selected_keys.add(
                self.theme.theme_key,
            )

        # Restore canonical catalog order instead of click order.
        self.owner_view.selected_theme_keys = tuple(
            theme.theme_key
            for theme in self.owner_view.questionnaire.themes
            if theme.theme_key in selected_keys
        )

        self.owner_view.refresh_theme_buttons()

        await interaction.response.edit_message(
            content=self.owner_view.format_content(),
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

        if len(questionnaire.themes) > MAX_THEME_BUTTONS:
            raise ValueError(
                (
                    "The Noctis button questionnaire supports "
                    f"at most {MAX_THEME_BUTTONS} themes."
                )
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

        for index, theme in enumerate(questionnaire.themes):
            row = index // THEME_BUTTONS_PER_ROW

            self.add_item(
                NoctisThemeButton(
                    owner_view=self,
                    theme=theme,
                    row=row,
                )
            )

        self._refresh_ai_button()

    def refresh_theme_buttons(self) -> None:
        """Refresh every theme button from current selection."""

        for child in self.children:
            if isinstance(
                child,
                NoctisThemeButton,
            ):
                child.refresh_from_view()

    def format_content(self) -> str:
        """Format the current questionnaire state."""

        themes_by_key = {theme.theme_key: theme for theme in self.questionnaire.themes}

        selected_labels = [
            themes_by_key[theme_key].label
            for theme_key in self.selected_theme_keys
            if theme_key in themes_by_key
        ]

        if selected_labels:
            selection_text = " • ".join(
                selected_labels,
            )
        else:
            selection_text = "Aucun"

        ai_text = "activés" if self.include_ai else "désactivés"

        if self.preview:
            header = (
                "**Aperçu du questionnaire Noctis**\n"
                "Mode test : aucune modification de rôle "
                "ne sera appliquée."
            )
        else:
            header = (
                "**Configuration de vos accès Noctis**\n"
                "Activez ou désactivez les catégories "
                "auxquelles vous souhaitez accéder."
            )

        return (
            f"{header}\n\n"
            f"**Accès sélectionnés ({len(selected_labels)}) :** "
            f"{selection_text}\n\n"
            f"**Contenus IA : {ai_text}**"
        )

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
        row=4,
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
            content=self.format_content(),
            view=self,
        )

    @discord.ui.button(
        label="Valider mes accès",
        style=discord.ButtonStyle.primary,
        row=4,
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
            await interaction.response.edit_message(
                content=self._format_preview(),
                view=None,
            )

            self.stop()
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette action doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        # Discord requires a quick acknowledgement.
        await interaction.response.defer()

        # Prevent duplicate submissions while role changes are running.
        for child in self.children:
            child.disabled = True

        await interaction.edit_original_response(
            content=(
                "⏳ **Mise à jour de vos accès Noctis...**\n\n"
                "Claviger applique votre sélection."
            ),
            view=self,
        )

        try:
            result = await self.coordinator.apply_selection(
                interaction.guild,
                interaction.user,
                self.policy,
                self.selected_theme_keys,
                include_ai=self.include_ai,
            )

        except Exception:
            for child in self.children:
                child.disabled = False

            await interaction.edit_original_response(
                content=(
                    "❌ **Impossible de mettre à jour vos accès "
                    "Noctis.**\n\n"
                    "Vous pouvez réessayer. Claviger recalculera "
                    "les modifications nécessaires depuis votre "
                    "état actuel."
                ),
                view=self,
            )
            return

        await interaction.edit_original_response(
            content=(
                "✅ **Vos accès Noctis ont été mis à jour.**\n\n"
                f"Modifications appliquées : {result.change_count}."
            ),
            view=None,
        )

        self.stop()

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
