import logging

import discord

from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireCatalogSubmission,
    WorkflowQuestionnaireSubmission,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.workflows.workflow_questionnaire_coordinator_service import (
    WorkflowQuestionnaireCoordinatorService,
)

logger = logging.getLogger(__name__)

MAX_MODAL_CATALOGS = 5
MAX_CATALOG_OPTIONS = 10


class WorkflowQuestionnaireUIError(ValueError):
    """Raised when a questionnaire cannot fit safely in Discord's modal UI."""


def _truncate(
    value: str,
    *,
    max_length: int,
) -> str:
    """Truncate one human-facing Discord component string."""

    if len(value) <= max_length:
        return value

    return f"{value[: max_length - 3]}..."


def _build_submission(
    questionnaire: WorkflowQuestionnaire,
    selected_by_catalog: dict[str, tuple[str, ...]],
) -> WorkflowQuestionnaireSubmission:
    """Build a submission containing the exact options that were presented."""

    return WorkflowQuestionnaireSubmission(
        catalogs=tuple(
            WorkflowQuestionnaireCatalogSubmission(
                catalog_key=catalog.catalog_key,
                visible_entry_keys=tuple(
                    option.entry_key
                    for option in catalog.options
                ),
                selected_entry_keys=selected_by_catalog.get(
                    catalog.catalog_key,
                    (),
                ),
            )
            for catalog in questionnaire.catalogs
        ),
        ai_preference=(
            questionnaire.ai_preference
            if questionnaire.ai_editable
            else None
        ),
    )


async def _emit_event(
    *,
    report_service: ReportService | None,
    interaction: discord.Interaction,
    event_type: str,
    severity: ReportSeverity,
    title: str,
    summary: str,
    details: str | None = None,
) -> None:
    """Emit best-effort questionnaire observability."""

    if report_service is None or interaction.guild is None:
        return

    try:
        await report_service.emit(
            ReportEvent(
                event_type=event_type,
                severity=severity,
                title=title,
                summary=summary,
                details=details,
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )
    except Exception:
        logger.exception(
            "Unable to emit questionnaire report event %s.",
            event_type,
        )


async def _apply(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowQuestionnaireCoordinatorService,
    questionnaire: WorkflowQuestionnaire,
    submission: WorkflowQuestionnaireSubmission,
    report_service: ReportService | None,
) -> None:
    """Apply one confirmed questionnaire after Discord has acknowledged it."""

    if interaction.guild is None or not isinstance(
        interaction.user,
        discord.Member,
    ):
        await interaction.edit_original_response(
            content="Ce questionnaire doit être utilisé sur un serveur.",
            view=None,
        )
        return

    try:
        result = await coordinator.apply_submission(
            guild=interaction.guild,
            member=interaction.user,
            workflow_key=questionnaire.workflow_key,
            submission=submission,
        )
    except Exception as error:
        logger.exception(
            "Questionnaire failed for guild %s workflow %s.",
            questionnaire.guild_id,
            questionnaire.workflow_key,
        )

        await _emit_event(
            report_service=report_service,
            interaction=interaction,
            event_type="workflow.questionnaire.failed",
            severity=ReportSeverity.ERROR,
            title="Échec du questionnaire workflow",
            summary=(
                f"Le questionnaire /{questionnaire.command_name} "
                "n'a pas pu appliquer les rôles."
            ),
            details=f"{type(error).__name__}: {error}",
        )

        await interaction.edit_original_response(
            content=(
                "❌ Impossible de mettre à jour tes rôles. "
                f"Relance /{questionnaire.command_name} et réessaie."
            ),
            view=None,
        )
        return

    await _emit_event(
        report_service=report_service,
        interaction=interaction,
        event_type="workflow.questionnaire.updated",
        severity=ReportSeverity.INFO,
        title="Questionnaire workflow appliqué",
        summary=(
            f"/{questionnaire.command_name} a appliqué "
            f"{result.change_count} modification(s) de rôle."
        ),
    )

    if result.change_count == 0:
        message = "✅ Tes choix sont déjà à jour."
    elif result.change_count == 1:
        message = "✅ Tes choix ont été mis à jour (1 modification)."
    else:
        message = (
            "✅ Tes choix ont été mis à jour "
            f"({result.change_count} modifications)."
        )

    await interaction.edit_original_response(
        content=message,
        view=None,
    )


class WorkflowQuestionnaireModal(discord.ui.Modal):
    """Display all catalog choices for one workflow."""

    def __init__(
        self,
        *,
        coordinator: WorkflowQuestionnaireCoordinatorService,
        questionnaire: WorkflowQuestionnaire,
        actor_id: int,
        report_service: ReportService | None,
    ) -> None:
        if not questionnaire.catalogs:
            raise WorkflowQuestionnaireUIError(
                "A questionnaire modal requires at least one catalog."
            )

        if len(questionnaire.catalogs) > MAX_MODAL_CATALOGS:
            raise WorkflowQuestionnaireUIError(
                "This workflow exposes too many catalogs for one Discord modal."
            )

        super().__init__(
            title=_truncate(
                questionnaire.title,
                max_length=45,
            ),
            timeout=600,
        )

        self.coordinator = coordinator
        self.questionnaire = questionnaire
        self.actor_id = actor_id
        self.report_service = report_service
        self.selection_groups: dict[str, discord.ui.CheckboxGroup] = {}

        for catalog in questionnaire.catalogs:
            if len(catalog.options) > MAX_CATALOG_OPTIONS:
                raise WorkflowQuestionnaireUIError(
                    f"Catalog {catalog.catalog_key!r} exposes more than "
                    f"{MAX_CATALOG_OPTIONS} options."
                )

            checkbox_options = [
                discord.CheckboxGroupOption(
                    label=_truncate(
                        (
                            f"{option.emoji} {option.label}"
                            if option.emoji
                            else option.label
                        ),
                        max_length=100,
                    ),
                    value=option.entry_key,
                    description=(
                        _truncate(
                            option.description,
                            max_length=100,
                        )
                        if option.description
                        else None
                    ),
                    default=option.selected,
                )
                for option in catalog.options
            ]

            group = discord.ui.CheckboxGroup(
                custom_id=f"workflow:{catalog.catalog_key}"[:100],
                options=checkbox_options,
                required=False,
                min_values=0,
                max_values=len(checkbox_options),
            )

            self.selection_groups[catalog.catalog_key] = group

            self.add_item(
                discord.ui.Label(
                    text=_truncate(
                        catalog.display_name,
                        max_length=45,
                    ),
                    description=(
                        _truncate(
                            catalog.description,
                            max_length=100,
                        )
                        if catalog.description
                        else "Choisis les options que tu souhaites conserver."
                    ),
                    component=group,
                )
            )

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        """Keep the questionnaire private to its original member."""

        if interaction.user.id == self.actor_id:
            return True

        await interaction.response.send_message(
            "Ce questionnaire appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return False

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Treat native modal submission as final confirmation."""

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        selected_by_catalog = {
            catalog_key: tuple(group.values)
            for catalog_key, group in self.selection_groups.items()
        }

        await _apply(
            interaction,
            coordinator=self.coordinator,
            questionnaire=self.questionnaire,
            submission=_build_submission(
                self.questionnaire,
                selected_by_catalog,
            ),
            report_service=self.report_service,
        )


class WorkflowQuestionnaireConfirmView(discord.ui.View):
    """Confirm a workflow that currently has no catalog choices."""

    def __init__(
        self,
        *,
        coordinator: WorkflowQuestionnaireCoordinatorService,
        questionnaire: WorkflowQuestionnaire,
        actor_id: int,
        report_service: ReportService | None,
    ) -> None:
        super().__init__(
            timeout=300,
        )
        self.coordinator = coordinator
        self.questionnaire = questionnaire
        self.actor_id = actor_id
        self.report_service = report_service

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.actor_id:
            return True

        await interaction.response.send_message(
            "Ce questionnaire appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Valider mes choix",
        style=discord.ButtonStyle.success,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        await _apply(
            interaction,
            coordinator=self.coordinator,
            questionnaire=self.questionnaire,
            submission=_build_submission(
                self.questionnaire,
                {},
            ),
            report_service=self.report_service,
        )


async def _open_choices(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowQuestionnaireCoordinatorService,
    questionnaire: WorkflowQuestionnaire,
    report_service: ReportService | None,
) -> None:
    """Open a catalog modal or a confirmation-only fallback."""

    if questionnaire.catalogs:
        await interaction.response.send_modal(
            WorkflowQuestionnaireModal(
                coordinator=coordinator,
                questionnaire=questionnaire,
                actor_id=interaction.user.id,
                report_service=report_service,
            )
        )
        return

    await interaction.response.send_message(
        (
            f"**{questionnaire.title}**\n\n"
            "Aucune option de catalogue n'est actuellement disponible. "
            "Tu peux quand même valider pour appliquer le rôle principal"
            + (
                " et ta préférence IA."
                if questionnaire.ai_editable
                else "."
            )
        ),
        view=WorkflowQuestionnaireConfirmView(
            coordinator=coordinator,
            questionnaire=questionnaire,
            actor_id=interaction.user.id,
            report_service=report_service,
        ),
        ephemeral=True,
    )


class WorkflowAIPreferenceView(discord.ui.View):
    """Collect AI preference only in the unique owner workflow."""

    def __init__(
        self,
        *,
        coordinator: WorkflowQuestionnaireCoordinatorService,
        questionnaire: WorkflowQuestionnaire,
        actor_id: int,
        report_service: ReportService | None,
    ) -> None:
        super().__init__(
            timeout=300,
        )
        self.coordinator = coordinator
        self.questionnaire = questionnaire
        self.actor_id = actor_id
        self.report_service = report_service

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.actor_id:
            return True

        await interaction.response.send_message(
            "Ce questionnaire appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return False

    async def _choose(
        self,
        interaction: discord.Interaction,
        *,
        enabled: bool,
    ) -> None:
        if interaction.guild is None or not isinstance(
            interaction.user,
            discord.Member,
        ):
            await interaction.response.send_message(
                "Ce questionnaire doit être utilisé sur un serveur.",
                ephemeral=True,
            )
            return

        try:
            questionnaire = await self.coordinator.build_questionnaire(
                guild=interaction.guild,
                member=interaction.user,
                workflow_key=self.questionnaire.workflow_key,
                ai_preference=enabled,
            )

            await _open_choices(
                interaction,
                coordinator=self.coordinator,
                questionnaire=questionnaire,
                report_service=self.report_service,
            )
        except Exception as error:
            logger.exception(
                "Unable to rebuild workflow %s after AI preference choice.",
                self.questionnaire.workflow_key,
            )

            await _emit_event(
                report_service=self.report_service,
                interaction=interaction,
                event_type="workflow.questionnaire.prepare_failed",
                severity=ReportSeverity.ERROR,
                title="Échec de préparation du questionnaire",
                summary=(
                    f"/{self.questionnaire.command_name} n'a pas pu être "
                    "reconstruit après le choix IA."
                ),
                details=f"{type(error).__name__}: {error}",
            )

            await interaction.response.send_message(
                "❌ Impossible de préparer le questionnaire avec ce choix IA.",
                ephemeral=True,
            )

    @discord.ui.button(
        label="Avec IA",
        style=discord.ButtonStyle.primary,
    )
    async def enable_ai(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self._choose(
            interaction,
            enabled=True,
        )

    @discord.ui.button(
        label="Sans IA",
        style=discord.ButtonStyle.secondary,
    )
    async def disable_ai(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        await self._choose(
            interaction,
            enabled=False,
        )


async def open_workflow_questionnaire(
    interaction: discord.Interaction,
    *,
    coordinator: WorkflowQuestionnaireCoordinatorService,
    questionnaire: WorkflowQuestionnaire,
    report_service: ReportService | None,
) -> None:
    """Open the generic questionnaire and its owner-only AI gate."""

    if questionnaire.ai_editable:
        current = "activée" if questionnaire.ai_preference else "désactivée"

        await interaction.response.send_message(
            (
                f"**{questionnaire.title} — préférence IA**\n\n"
                "Ce workflow est l'unique propriétaire de la préférence IA "
                "globale du serveur.\n"
                f"Préférence actuelle : **{current}**.\n\n"
                "Choisis l'état à utiliser avant d'ouvrir le questionnaire."
            ),
            view=WorkflowAIPreferenceView(
                coordinator=coordinator,
                questionnaire=questionnaire,
                actor_id=interaction.user.id,
                report_service=report_service,
            ),
            ephemeral=True,
        )
        return

    await _open_choices(
        interaction,
        coordinator=coordinator,
        questionnaire=questionnaire,
        report_service=report_service,
    )
