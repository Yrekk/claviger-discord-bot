import discord
from discord import app_commands

from claviger.commands.admin.diagnostic_output import send_ephemeral_diagnostic
from claviger.models.runtime.workflow_catalog_diagnostic_model import (
    GuildCatalogDiagnosticResult,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)
from claviger.services.runtime.workflow_catalog_diagnostic_service import (
    WorkflowCatalogDiagnosticService,
)
from claviger.ui.catalogs.catalog_metadata_view import (
    open_next_catalog_metadata,
)

_SEPARATOR = "============="


def _format_name_list(
    names: tuple[str, ...],
    *,
    empty: str = "aucun",
) -> str:
    if not names:
        return empty

    return ", ".join(
        names,
    )


def _format_catalog_state(
    catalog,
) -> str:
    """Return one concise status describing the catalog problem class."""

    states: list[str] = []

    if catalog.incomplete_entries:
        states.append(
            "MÉTADONNÉES INCOMPLÈTES"
        )

    if catalog.unsynced_role_names:
        states.append(
            "SYNCHRONISATION REQUISE"
        )

    if catalog.role_issues:
        states.append(
            "ANOMALIES DÉTECTÉES"
        )

    if not states:
        return "✅ READY"

    return "⚠️ " + " + ".join(
        states,
    )


def _format_catalog_diagnostic(
    result: GuildCatalogDiagnosticResult,
) -> list[str]:
    """Format workflow/catalog readiness around actionable problem classes."""

    lines = [
        "**Diagnostic des catalogues et workflows**",
        f"- Workflows configurés : {len(result.workflows)}",
    ]

    if not result.workflows:
        lines.extend(
            [
                "",
                "Aucun workflow configuré sur ce serveur.",
            ]
        )
        return lines

    for workflow in result.workflows:
        structure_state = (
            "❌ À CORRIGER"
            if workflow.structure_issues
            else "✅ VALIDE"
        )

        command_name = workflow.command_name.strip()
        if not workflow.enabled:
            command_state = (
                f"⏸ /{command_name} — workflow désactivé"
                if command_name
                else "⏸ workflow désactivé"
            )
        elif command_name:
            command_state = f"✅ /{command_name} configurée"
        else:
            command_state = "❌ aucune commande configurée"

        lines.extend(
            [
                "",
                _SEPARATOR,
                f"**Workflow — {workflow.title}**",
                f"- Structure : {structure_state}",
                f"- Commande : {command_state}",
                (
                    f"- Catégorie : {workflow.category_name}"
                    if workflow.category_name
                    else "- Catégorie : ❌ absente ou non configurée"
                ),
                (
                    f"- Salon de gestion : #{workflow.management_channel_name}"
                    if workflow.management_channel_name
                    else "- Salon de gestion : ❌ absent ou non configuré"
                ),
                (
                    "- Salon(s) d'exécution : "
                    + _format_name_list(
                        tuple(
                            f"#{name}"
                            for name in workflow.execution_channel_names
                        ),
                    )
                ),
                (
                    f"- Rôle principal : {workflow.primary_role_name}"
                    if workflow.primary_role_name
                    else "- Rôle principal : ❌ absent ou non configuré"
                ),
                (
                    "- Visibilité explicite du rôle principal : "
                    + _format_name_list(
                        tuple(
                            f"#{name}"
                            for name
                            in workflow.primary_role_explicit_channel_names
                        ),
                    )
                ),
                (
                    "- Propriétaire de la question IA : "
                    + (
                        "✅ oui"
                        if workflow.ai_questionnaire_owner
                        else "non"
                    )
                ),
            ]
        )

        if workflow.structure_issues:
            lines.extend(
                [
                    "",
                    "**⚠️ Problèmes de structure**",
                    *(
                        f"- {issue}"
                        for issue in workflow.structure_issues
                    ),
                ]
            )

        if not workflow.catalogs:
            lines.extend(
                [
                    "",
                    "**Catalogue**",
                    "- État catalogue : ❌ AUCUN CATALOGUE ACTIF LIÉ",
                ]
            )
            continue

        for catalog in workflow.catalogs:
            lines.extend(
                [
                    "",
                    f"**Catalogue — {catalog.display_name}**",
                    f"- État catalogue : {_format_catalog_state(catalog)}",
                    f"- Pattern : {catalog.role_prefix}",
                ]
            )

            if (
                catalog.incomplete_entries
                or catalog.unsynced_role_names
                or catalog.role_issues
            ):
                lines.extend(
                    [
                        "",
                        "**⚠️ Problèmes détectés**",
                    ]
                )

            for entry in catalog.incomplete_entries:
                label = entry.label or entry.entry_key
                missing = ", ".join(
                    entry.missing_fields,
                )
                roles = _format_name_list(
                    entry.target_role_names,
                )
                lines.append(
                    (
                        f"- {label} : {missing} manquant(s) "
                        f"— rôles {roles}"
                    )
                )

            if catalog.unsynced_role_names:
                lines.append(
                    (
                        "- Synchronisation BDD requise pour : "
                        + _format_name_list(
                            catalog.unsynced_role_names,
                        )
                    )
                )

            for issue in catalog.role_issues:
                reasons = "; ".join(
                    issue.reasons,
                )
                channels = _format_name_list(
                    tuple(
                        f"#{name}"
                        for name in issue.channel_names
                    ),
                )
                lines.append(
                    (
                        f"- {issue.role_name} : {reasons} "
                        f"— salons {channels}"
                    )
                )

            lines.extend(
                [
                    "",
                    "**Résumé catalogue**",
                    f"- Rôles Discord détectés : {len(catalog.detected_role_names)}",
                    (
                        "- Salons/forums liés aux rôles : "
                        f"{len(catalog.linked_channel_names)}"
                    ),
                    (
                        "- Salons/forums : "
                        + _format_name_list(
                            tuple(
                                f"#{name}"
                                for name in catalog.linked_channel_names
                            )
                        )
                    ),
                    f"- Entrées BDD : {catalog.entry_count}",
                    (
                        "- Métadonnées questionnaire complètes : "
                        f"{catalog.complete_entry_count} / {catalog.entry_count}"
                    ),
                    (
                        "- Entrées metadata incomplètes : "
                        f"{len(catalog.incomplete_entries)}"
                    ),
                    (
                        "- Rôles détectés absents de la BDD : "
                        f"{len(catalog.unsynced_role_names)}"
                    ),
                ]
            )

    return lines


def create_catalog_group(
    diagnostic_service: WorkflowCatalogDiagnosticService,
    report_service: ReportService,
    administration_service: CatalogAdministrationService | None = None,
) -> app_commands.Group:
    """Create owner-only workflow catalog diagnostics and administration."""

    catalog_group = app_commands.Group(
        name="catalog",
        description="Diagnostic des catalogues de workflows.",
    )

    @catalog_group.command(
        name="scan",
        description="Inspecte les workflows, catalogues et métadonnées.",
    )
    async def scan_catalogs(
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
            result = await diagnostic_service.inspect(
                interaction.guild,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="catalog.scan.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du diagnostic des catalogues",
                    summary=(
                        "L'application n'a pas pu inspecter "
                        "les catalogues de workflows."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                f"Impossible d'inspecter les catalogues : {error}",
                ephemeral=True,
            )
            return

        await send_ephemeral_diagnostic(
            interaction,
            _format_catalog_diagnostic(
                result,
            ),
        )

    if administration_service is not None:

        @catalog_group.command(
            name="sync",
            description="Synchronise les catalogues actifs depuis Discord.",
        )
        async def sync_catalogs(
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

            summaries = await administration_service.synchronize_all(
                interaction.guild,
            )

            if not summaries:
                await interaction.followup.send(
                    "Aucun catalogue actif n'est lié à un workflow actif.",
                    ephemeral=True,
                )
                return

            lines = [
                "**Synchronisation des catalogues**",
            ]
            failed = False

            for summary in summaries:
                lines.append(
                    "============="
                )
                lines.append(
                    f"**{summary.display_name}** — pattern "
                    f"`{summary.role_prefix}`"
                )

                if not summary.succeeded:
                    failed = True
                    lines.append(
                        f"- ❌ Échec : {summary.error}"
                    )
                    continue

                lines.extend(
                    [
                        f"- ✅ Entrées techniques : {summary.entry_count}",
                        (
                            "- Métadonnées incomplètes : "
                            f"{summary.incomplete_metadata_count}"
                        ),
                    ]
                )

            severity = (
                ReportSeverity.WARNING
                if failed
                else ReportSeverity.INFO
            )
            await report_service.emit(
                ReportEvent(
                    event_type="catalog.sync.completed",
                    severity=severity,
                    title="Synchronisation catalogue terminée",
                    summary=(
                        "Au moins un catalogue a échoué."
                        if failed
                        else "Tous les catalogues actifs ont été synchronisés."
                    ),
                    details="\n".join(
                        lines,
                    ),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await send_ephemeral_diagnostic(
                interaction,
                lines,
            )

        @catalog_group.command(
            name="next",
            description="Configure la prochaine entrée catalogue incomplète.",
        )
        async def next_catalog_metadata(
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
                await open_next_catalog_metadata(
                    interaction,
                    service=administration_service,
                    report_service=report_service,
                )
            except Exception as error:
                await report_service.emit(
                    ReportEvent(
                        event_type="catalog.metadata.prepare_failed",
                        severity=ReportSeverity.ERROR,
                        title="Échec de préparation des métadonnées catalogue",
                        summary=(
                            "La prochaine entrée incomplète n'a pas pu "
                            "être préparée."
                        ),
                        details=f"{type(error).__name__}: {error}",
                        guild_id=interaction.guild.id,
                        guild_label=interaction.guild.name,
                        actor_id=interaction.user.id,
                        actor_label=interaction.user.display_name,
                    )
                )

                if interaction.response.is_done():
                    await interaction.followup.send(
                        "Impossible de préparer la prochaine entrée.",
                        ephemeral=True,
                    )
                else:
                    await interaction.response.send_message(
                        "Impossible de préparer la prochaine entrée.",
                        ephemeral=True,
                    )

    return catalog_group
