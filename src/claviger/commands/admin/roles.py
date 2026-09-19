import discord
from discord import app_commands

from claviger.commands.admin.diagnostic_output import send_ephemeral_diagnostic
from claviger.models.runtime.guild_role_diagnostic_model import (
    GuildRoleDiagnosticResult,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.guild_role_diagnostic_service import (
    GuildRoleDiagnosticService,
)


def _format_roles(roles: list[discord.Role]) -> list[str]:
    """Format one role collection for the owner-only diagnostic output."""

    if not roles:
        return ["- Aucun"]

    return [
        f"- {role.name} (`{role.id}`)"
        for role in roles
    ]


def _format_role_diagnostic(
    result: GuildRoleDiagnosticResult,
) -> list[str]:
    """Format workflow-aware role diagnostics without Discord IDs."""

    if result.ai_enabled is None:
        ai_state = "non configurée"
    elif result.ai_enabled:
        ai_state = "activée"
    else:
        ai_state = "désactivée"

    if result.ai_role_missing:
        ai_role = "❌ rôle configuré introuvable"
    elif result.ai_role_name is None:
        ai_role = "aucun"
    else:
        ai_role = result.ai_role_name

    def section(
        title: str,
        names: tuple[str, ...],
    ) -> list[str]:
        lines = [
            f"**{title} ({len(names)})**",
        ]

        if not names:
            lines.append(
                "- Aucun"
            )
            return lines

        lines.extend(
            f"- {name}"
            for name in names
        )
        return lines

    lines = [
        "**Diagnostic des rôles**",
        f"- Rôle de l'application : {result.bot_role_name}",
        f"- IA globale : {ai_state}",
        f"- Rôle IA : {ai_role}",
        "",
        *section(
            "Rôles principaux de workflow",
            result.workflow_primary_role_names,
        ),
        "",
        *section(
            "Rôles catalogue configurés",
            result.configured_catalog_role_names,
        ),
        "",
        f"**Anomalies de pattern ({len(result.pattern_anomalies)})**",
    ]

    if not result.pattern_anomalies:
        lines.append(
            "- Aucune"
        )
    else:
        for anomaly in result.pattern_anomalies:
            workflows = ", ".join(
                anomaly.workflow_labels,
            )
            reasons = "; ".join(
                anomaly.reasons,
            )
            channels = (
                ", ".join(
                    f"#{name}"
                    for name in anomaly.channel_names
                )
                if anomaly.channel_names
                else "aucun"
            )
            lines.append(
                f"- {anomaly.role_name} [{workflows}] : "
                f"{reasons} — salons {channels}"
            )

    lines.extend(
        [
            "",
            *section(
                "Rôles manipulables hors workflows",
                result.unconfigured_manageable_role_names,
            ),
            "",
            *section(
                "Rôles non manipulables",
                result.unmanageable_role_names,
            ),
        ]
    )

    return lines


def create_roles_group(
    role_discovery_service: RoleDiscoveryService,
    report_service: ReportService,
    diagnostic_service: GuildRoleDiagnosticService | None = None,
) -> app_commands.Group:
    """Create the workflow-agnostic role administration command group."""

    roles_group = app_commands.Group(
        name="roles",
        description="Analyse la hiérarchie des rôles Discord.",
    )

    @roles_group.command(
        name="scan",
        description="Analyse la hiérarchie technique des rôles du serveur.",
    )
    async def scan_roles(
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
            diagnostic = (
                await diagnostic_service.inspect(
                    interaction.guild,
                )
                if diagnostic_service is not None
                else None
            )

            hierarchy = (
                await role_discovery_service.get_hierarchy(
                    interaction.guild,
                )
                if diagnostic is None
                else None
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="roles.scan.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du scan des rôles",
                    summary=("L'application n'a pas pu analyser la hiérarchie des rôles."),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                f"Impossible d'analyser les rôles : {error}",
                ephemeral=True,
            )
            return

        if diagnostic is not None:
            await send_ephemeral_diagnostic(
                interaction,
                _format_role_diagnostic(
                    diagnostic,
                ),
            )
            return

        if hierarchy is None:
            raise RuntimeError("Role hierarchy diagnostic is unavailable.")

        lines = [
            f"**Rôle de l'application :** {hierarchy.bot_role.name} "
            f"({hierarchy.bot_role.id})",
            "",
            f"**Rôles de confiance ({len(hierarchy.trusted_roles)})**",
            *_format_roles(hierarchy.trusted_roles),
            "",
            (
                "**Rôles techniquement manipulables "
                f"({len(hierarchy.manageable_roles)})**"
            ),
            *_format_roles(hierarchy.manageable_roles),
            "",
            f"**Rôles non manipulables ({len(hierarchy.unmanageable_roles)})**",
            *_format_roles(hierarchy.unmanageable_roles),
            "",
            (
                "Ce scan décrit uniquement la hiérarchie Discord. "
                "L'éligibilité d'un rôle pour un workflow est calculée "
                "séparément à partir de la configuration persistée."
            ),
        ]

        await interaction.followup.send(
            "\n".join(lines),
            ephemeral=True,
        )

    return roles_group
