import logging

import discord

from claviger.models.catalogs.catalog_administration_model import (
    CatalogMetadataCandidate,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)

logger = logging.getLogger(__name__)


def _candidate_context(
    candidate: CatalogMetadataCandidate,
) -> str:
    """Render the technical identity without exposing raw Discord IDs."""

    roles = ", ".join(
        candidate.target_role_names,
    ) or "aucun"
    channels = ", ".join(
        f"#{name}"
        for name in candidate.target_channel_names
    ) or "aucun"

    return (
        f"Catalogue : **{candidate.catalog_display_name}**\n"
        f"Entrée : `{candidate.entry_key}`\n"
        f"Rôle(s) : {roles}\n"
        f"Salon(s) : {channels}"
    )


async def _reject_foreign_actor(
    interaction: discord.Interaction,
    *,
    actor_id: int,
    guild_id: int,
) -> bool:
    """Keep one metadata flow scoped to its original owner and guild."""

    if interaction.user.id != actor_id:
        await interaction.response.send_message(
            "Cette configuration appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return True

    if interaction.guild is None or interaction.guild.id != guild_id:
        await interaction.response.send_message(
            "Cette configuration doit rester sur son serveur d'origine.",
            ephemeral=True,
        )
        return True

    return False


class CatalogMetadataModal(discord.ui.Modal):
    """Edit only the human metadata of one logical catalog entry."""

    def __init__(
        self,
        *,
        service: CatalogAdministrationService,
        report_service: ReportService,
        candidate: CatalogMetadataCandidate,
        actor_id: int,
        guild_id: int,
    ) -> None:
        title = f"Métadonnées — {candidate.entry_key}"[:45]

        super().__init__(
            title=title,
            timeout=600,
        )

        self.service = service
        self.report_service = report_service
        self.candidate = candidate
        self.actor_id = actor_id
        self.guild_id = guild_id

        self.label_input = discord.ui.TextInput(
            label="Label du questionnaire",
            default=candidate.label or candidate.entry_key,
            min_length=1,
            max_length=100,
        )
        self.description_input = discord.ui.TextInput(
            label="Description",
            default=candidate.description or "",
            style=discord.TextStyle.paragraph,
            min_length=1,
            max_length=100,
        )
        self.emoji_input = discord.ui.TextInput(
            label="Emoji (facultatif)",
            default=candidate.emoji or "",
            required=False,
            max_length=100,
        )

        self.add_item(
            self.label_input,
        )
        self.add_item(
            self.description_input,
        )
        self.add_item(
            self.emoji_input,
        )

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Persist metadata, then offer the next incomplete entry."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        if interaction.guild is None:
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            next_candidate = await self.service.update_metadata(
                guild_id=self.guild_id,
                catalog_key=self.candidate.catalog_key,
                entry_key=self.candidate.entry_key,
                label=str(
                    self.label_input.value,
                ),
                description=str(
                    self.description_input.value,
                ),
                emoji=str(
                    self.emoji_input.value,
                ),
            )
        except ValueError as error:
            await interaction.followup.send(
                f"Impossible d'enregistrer ces métadonnées : {error}",
                ephemeral=True,
            )
            return
        except Exception as error:
            logger.exception(
                "Unexpected catalog metadata update failure for guild %s.",
                self.guild_id,
            )
            await self.report_service.emit(
                ReportEvent(
                    event_type="catalog.metadata.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de configuration des métadonnées catalogue",
                    summary=(
                        "Une entrée catalogue n'a pas pu être mise à jour."
                    ),
                    details=(
                        f"{type(error).__name__}: {error}\n"
                        f"catalog={self.candidate.catalog_key}\n"
                        f"entry={self.candidate.entry_key}"
                    ),
                    guild_id=self.guild_id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )
            await interaction.followup.send(
                "Impossible d'enregistrer ces métadonnées.",
                ephemeral=True,
            )
            return

        await self.report_service.emit(
            ReportEvent(
                event_type="catalog.metadata.updated",
                severity=ReportSeverity.INFO,
                title="Métadonnées catalogue mises à jour",
                summary=(
                    f"{self.candidate.catalog_display_name} / "
                    f"{self.candidate.entry_key} est configurée."
                ),
                guild_id=self.guild_id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        if next_candidate is None:
            await interaction.followup.send(
                (
                    "✅ **Métadonnées enregistrées.**\n\n"
                    "Toutes les entrées actives ont maintenant un label "
                    "et une description. Relance `catalog scan` pour "
                    "contrôler l'état complet."
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            (
                "✅ **Métadonnées enregistrées.**\n\n"
                "Entrée suivante à compléter :\n"
                f"{_candidate_context(next_candidate)}"
            ),
            ephemeral=True,
            view=CatalogMetadataNextView(
                service=self.service,
                report_service=self.report_service,
                candidate=next_candidate,
                actor_id=self.actor_id,
                guild_id=self.guild_id,
            ),
        )


class CatalogMetadataNextView(discord.ui.View):
    """Allow the administrator to continue the metadata queue."""

    def __init__(
        self,
        *,
        service: CatalogAdministrationService,
        report_service: ReportService,
        candidate: CatalogMetadataCandidate,
        actor_id: int,
        guild_id: int,
    ) -> None:
        super().__init__(
            timeout=600,
        )

        self.service = service
        self.report_service = report_service
        self.candidate = candidate
        self.actor_id = actor_id
        self.guild_id = guild_id

    @discord.ui.button(
        label="Configurer l'entrée suivante",
        style=discord.ButtonStyle.primary,
    )
    async def configure_next(
        self,
        interaction: discord.Interaction,
        _: discord.ui.Button,
    ) -> None:
        """Open the next metadata modal without synchronizing targets."""

        if await _reject_foreign_actor(
            interaction,
            actor_id=self.actor_id,
            guild_id=self.guild_id,
        ):
            return

        await interaction.response.send_modal(
            CatalogMetadataModal(
                service=self.service,
                report_service=self.report_service,
                candidate=self.candidate,
                actor_id=self.actor_id,
                guild_id=self.guild_id,
            )
        )


async def open_next_catalog_metadata(
    interaction: discord.Interaction,
    *,
    service: CatalogAdministrationService,
    report_service: ReportService,
) -> bool:
    """Open the first incomplete metadata entry, if one exists."""

    if interaction.guild is None:
        return False

    candidate = await service.next_incomplete(
        interaction.guild.id,
    )

    if candidate is None:
        await interaction.response.send_message(
            (
                "✅ Toutes les entrées actives possèdent déjà un label "
                "et une description."
            ),
            ephemeral=True,
        )
        return False

    await interaction.response.send_modal(
        CatalogMetadataModal(
            service=service,
            report_service=report_service,
            candidate=candidate,
            actor_id=interaction.user.id,
            guild_id=interaction.guild.id,
        )
    )

    return True
