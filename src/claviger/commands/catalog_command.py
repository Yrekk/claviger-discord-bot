import discord
from discord import app_commands

from claviger.database.status import DatabaseState, DatabaseStatusService
from claviger.models.catalog_sync_result_model import CatalogSyncResult
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.services.catalog_sync_coordinator_service import (
    CatalogSyncCoordinatorService,
)
from claviger.ui.catalog_metadata_modal import CatalogMetadataModal


def _format_catalog_sync_result(
    result: CatalogSyncResult,
) -> str:
    """Format a catalog synchronization result for Discord."""

    lines = [
        "**Synchronisation des catalogues**",
        "",
    ]

    warning_labels = {
        "missing_channel_mapping": "aucun channel associé",
        "ambiguous_channel_mapping": "plusieurs channels associés",
    }

    for catalog in result.catalogs:
        plan = catalog.plan

        lines.extend(
            [
                f"**{catalog.display_name}**",
                f"- Créés : {len(plan.creates)}",
                f"- Actualisés : {len(plan.refreshes)}",
                f"- États mis à jour : {len(plan.state_updates)}",
                f"- Avertissements : {len(plan.warnings)}",
            ]
        )

        for warning in plan.warnings:
            warning_label = warning_labels.get(
                warning.code,
                warning.code,
            )

            lines.append(f"  - `{warning.role_name}` : {warning_label}")

        lines.append("")

    lines.extend(
        [
            f"**Total des modifications : {result.change_count}**",
            f"**Total des avertissements : {result.warning_count}**",
        ]
    )

    if result.change_count == 0 and result.warning_count == 0:
        lines.extend(
            [
                "",
                "Les catalogues sont déjà synchronisés.",
            ]
        )

    return "\n".join(lines)


def create_catalog_group(
    catalog_sync_coordinator_service: CatalogSyncCoordinatorService,
    catalog_next_coordinator_service: CatalogNextCoordinatorService,
    policy_resolver: PolicyResolver,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's catalog administration command group."""

    catalog_group = app_commands.Group(
        name="catalog",
        description="Synchronisation et configuration des catalogues.",
    )

    @catalog_group.command(
        name="sync",
        description="Synchronise les catalogues avec la configuration Discord.",
    )
    async def catalog_sync(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            status = await database_status_service.check()

            if status.state != DatabaseState.READY:
                await interaction.followup.send(
                    (
                        "La base de données doit être prête avant "
                        "de synchroniser les catalogues. "
                        "Vérifie `/claviger database status`."
                    ),
                    ephemeral=True,
                )
                return

            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

            result = await catalog_sync_coordinator_service.sync(
                interaction.guild,
                policy,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="catalog.sync.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la synchronisation des catalogues",
                    summary=(
                        "Claviger n'a pas pu synchroniser les catalogues Discord."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Échec de la synchronisation des catalogues.",
                ephemeral=True,
            )
            return

        formatted_result = _format_catalog_sync_result(
            result,
        )

        await report_service.emit(
            ReportEvent(
                event_type="catalog.sync.success",
                severity=ReportSeverity.INFO,
                title="Catalogues synchronisés",
                summary=("Les catalogues Discord ont été synchronisés avec succès."),
                details=formatted_result,
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            formatted_result,
            ephemeral=True,
        )

    @catalog_group.command(
        name="next",
        description="Configure la prochaine entrée de catalogue incomplète.",
    )
    async def catalog_next(
        interaction: discord.Interaction,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Cette commande doit être utilisée sur un serveur.",
                ephemeral=True,
            )
            return

        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "Cette commande est réservée au propriétaire du serveur.",
                ephemeral=True,
            )
            return

        try:
            status = await database_status_service.check()

            if status.state != DatabaseState.READY:
                await interaction.response.send_message(
                    (
                        "La base de données doit être prête avant "
                        "de configurer les catalogues. "
                        "Vérifie `/claviger database status`."
                    ),
                    ephemeral=True,
                )
                return

            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

            selection = await catalog_next_coordinator_service.get_next(
                interaction.guild.id,
                policy,
            )

            if selection is None:
                await interaction.response.send_message(
                    "Tous les catalogues disponibles sont configurés.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_modal(
                CatalogMetadataModal(
                    coordinator=catalog_next_coordinator_service,
                    policy=policy,
                    selection=selection,
                    actor_id=interaction.user.id,
                )
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="catalog.next.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la configuration du catalogue",
                    summary=(
                        "Claviger n'a pas pu déterminer "
                        "la prochaine entrée à configurer."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.response.send_message(
                "Impossible de déterminer la prochaine entrée à configurer.",
                ephemeral=True,
            )

    return catalog_group
