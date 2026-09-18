import discord

from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)

MAX_WORKFLOW_OPTIONS = 25


async def _reject_foreign_actor(
    interaction: discord.Interaction,
    *,
    actor_id: int,
    guild_id: int,
) -> bool:
    if interaction.user.id != actor_id:
        await interaction.response.send_message(
            "Cette configuration appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return True

    if interaction.guild is None or interaction.guild.id != guild_id:
        await interaction.response.send_message(
            "Cette action doit rester sur le serveur qui l'a créée.",
            ephemeral=True,
        )
        return True

    return False


class _WorkflowOwnerSelect(discord.ui.Select):
    """Select the single workflow allowed to edit the guild AI preference."""

    def __init__(
        self,
        *,
        workflows: tuple[WorkflowDefinition, ...],
        current_owner_key: str | None,
    ) -> None:
        candidates = tuple(
            workflow
            for workflow in workflows
            if workflow.workflow_key != current_owner_key
        )

        if not candidates:
            raise ValueError("No alternate workflow is available for AI ownership.")

        if len(candidates) > MAX_WORKFLOW_OPTIONS:
            raise ValueError(
                "Discord select menus support at most 25 workflow choices."
            )

        super().__init__(
            placeholder="Choisir le workflow qui proposera l'option IA",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label=f"/{workflow.command_name}"[:100],
                    value=workflow.workflow_key,
                    description=workflow.title[:100],
                )
                for workflow in candidates
            ],
        )

    async def callback(
        self,
        interaction: discord.Interaction,
    ) -> None:
        view = self.view

        if not isinstance(
            view,
            WorkflowAIQuestionnaireOwnerSelectionView,
        ):
            raise RuntimeError("AI questionnaire owner select is detached.")

        if await _reject_foreign_actor(
            interaction,
            actor_id=view.actor_id,
            guild_id=view.guild_id,
        ):
            return

        await interaction.response.defer()

        selected_key = self.values[0]

        try:
            previous_owner, current_owner = await view.owner_service.assign(
                guild_id=view.guild_id,
                workflow_key=selected_key,
            )

        except Exception as error:
            await view.report_service.emit(
                ReportEvent(
                    event_type="workflow.ai_questionnaire.assign_failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du changement de questionnaire IA",
                    summary=(
                        "Claviger n'a pas pu déplacer la question de préférence IA."
                    ),
                    details=str(error),
                    guild_id=view.guild_id,
                    guild_label=(
                        interaction.guild.name
                        if interaction.guild is not None
                        else None
                    ),
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.edit_original_response(
                content=(
                    "❌ Impossible de changer le workflow propriétaire "
                    "du questionnaire IA."
                ),
                view=None,
            )
            return

        selected = next(
            workflow
            for workflow in view.workflows
            if workflow.workflow_key == current_owner
        )

        await view.report_service.emit(
            ReportEvent(
                event_type="workflow.ai_questionnaire.owner_changed",
                severity=ReportSeverity.INFO,
                title="Workflow du questionnaire IA modifié",
                summary=(
                    f"/{selected.command_name} est maintenant l'unique workflow "
                    "qui propose la préférence IA."
                ),
                details=(
                    f"Ancien propriétaire : {previous_owner or 'aucun'}\n"
                    f"Nouveau propriétaire : {current_owner}"
                ),
                guild_id=view.guild_id,
                guild_label=(
                    interaction.guild.name
                    if interaction.guild is not None
                    else None
                ),
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        view.stop()

        await interaction.edit_original_response(
            content=(
                "✅ **Questionnaire IA configuré.**\n\n"
                f"/{selected.command_name} est désormais l'unique workflow "
                "autorisé à proposer l'option IA.\n"
                "Les autres workflows consommeront uniquement l'état du rôle IA."
            ),
            view=None,
        )


class WorkflowAIQuestionnaireOwnerSelectionView(discord.ui.View):
    """Expose the explicit workflow owner selection."""

    def __init__(
        self,
        *,
        owner_service: GuildAIQuestionnaireOwnerService,
        report_service: ReportService,
        workflows: tuple[WorkflowDefinition, ...],
        actor_id: int,
        guild_id: int,
        current_owner_key: str | None,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.owner_service = owner_service
        self.report_service = report_service
        self.workflows = workflows
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.current_owner_key = current_owner_key

        self.add_item(
            _WorkflowOwnerSelect(
                workflows=workflows,
                current_owner_key=current_owner_key,
            )
        )


class WorkflowAIQuestionnaireOwnerCurrentView(discord.ui.View):
    """Ask for confirmation before replacing an existing owner."""

    def __init__(
        self,
        *,
        owner_service: GuildAIQuestionnaireOwnerService,
        report_service: ReportService,
        workflows: tuple[WorkflowDefinition, ...],
        actor_id: int,
        guild_id: int,
        current_owner_key: str,
    ) -> None:
        super().__init__(
            timeout=300,
        )

        self.owner_service = owner_service
        self.report_service = report_service
        self.workflows = workflows
        self.actor_id = actor_id
        self.guild_id = guild_id
        self.current_owner_key = current_owner_key

    @discord.ui.button(
        label="Changer le workflow",
        style=discord.ButtonStyle.primary,
    )
    async def change_owner(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        alternatives = tuple(
            workflow
            for workflow in self.workflows
            if workflow.workflow_key != self.current_owner_key
        )

        if not alternatives:
            await interaction.response.edit_message(
                content=(
                    "Aucun autre workflow actif n'est disponible. "
                    "Le propriétaire IA actuel reste inchangé."
                ),
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=(
                "**Changer le questionnaire IA**\n\n"
                "Choisis le nouveau workflow propriétaire. "
                "Le changement est atomique : l'ancien cesse immédiatement "
                "d'être propriétaire quand le nouveau est enregistré."
            ),
            view=WorkflowAIQuestionnaireOwnerSelectionView(
                owner_service=self.owner_service,
                report_service=self.report_service,
                workflows=self.workflows,
                actor_id=self.actor_id,
                guild_id=self.guild_id,
                current_owner_key=self.current_owner_key,
            ),
        )
