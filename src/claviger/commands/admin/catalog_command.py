import discord
from discord import app_commands

from claviger.commands.admin.diagnostic_output import send_ephemeral_diagnostic
from claviger.models.runtime.workflow_catalog_diagnostic_model import (
    GuildCatalogDiagnosticResult,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.runtime.workflow_catalog_diagnostic_service import (
    WorkflowCatalogDiagnosticService,
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


def _format_catalog_diagnostic(
    result: GuildCatalogDiagnosticResult,
) -> list[str]:
    """Format workflow/catalog readiness without exposing Discord IDs."""

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
        workflow_has_issues = bool(
            workflow.structure_issues
            or not workflow.catalogs
            or any(
                catalog.incomplete_entries
                or catalog.unsynced_role_names
                or catalog.role_issues
                for catalog in workflow.catalogs
            )
        )
        if not workflow.enabled:
            workflow_state = "⏸ DÉSACTIVÉ"
        elif workflow_has_issues:
            workflow_state = "⚠️ À CORRIGER"
        else:
            workflow_state = "✅ READY"

        lines.extend(
            [
                "",
                _SEPARATOR,
                f"**Workflow — {workflow.title}**",
                f"- État : {workflow_state}",
                f"- Commande : /{workflow.command_name}",
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
            lines.append(
                "- Anomalies structure : "
                + "; ".join(
                    workflow.structure_issues,
                )
            )

        if not workflow.catalogs:
            lines.append(
                "- Catalogue : ❌ aucun catalogue actif lié"
            )
            continue

        for catalog in workflow.catalogs:
            catalog_has_issues = bool(
                catalog.incomplete_entries
                or catalog.unsynced_role_names
                or catalog.role_issues
            )
            catalog_state = (
                "⚠️ À CORRIGER"
                if catalog_has_issues
                else "✅ READY"
            )

            lines.extend(
                [
                    "",
                    f"**Catalogue — {catalog.display_name}**",
                    f"- État : {catalog_state}",
                    f"- Pattern : {catalog.role_prefix}",
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
                        "- Entrées metadata complètes : "
                        f"{catalog.complete_entry_count}"
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

            if catalog.incomplete_entries:
                incomplete_role_names = tuple(
                    sorted(
                        {
                            role_name
                            for entry in catalog.incomplete_entries
                            for role_name in entry.target_role_names
                        },
                        key=str.casefold,
                    )
                )
                lines.append(
                    (
                        "- Rôles concernés par des métadonnées incomplètes : "
                        f"{len(incomplete_role_names)}"
                    )
                )
                lines.append(
                    "**À compléter pour le questionnaire**"
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
                        f"- {label} : {missing} manquant(s) — rôles {roles}"
                    )

            if catalog.unsynced_role_names:
                lines.append(
                    "**Rôles nécessitant une synchronisation**"
                )
                lines.extend(
                    f"- {role_name}"
                    for role_name in catalog.unsynced_role_names
                )

            if catalog.role_issues:
                lines.append(
                    "**Anomalies catalogue**"
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
                        f"- {issue.role_name} : {reasons} — salons {channels}"
                    )

    return lines


def create_catalog_group(
    diagnostic_service: WorkflowCatalogDiagnosticService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create owner-only workflow catalog diagnostics."""

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

    return catalog_group
