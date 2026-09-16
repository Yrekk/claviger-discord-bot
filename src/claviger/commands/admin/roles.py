import discord
from discord import app_commands

from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.role_discovery import RoleDiscoveryService


def _format_roles(roles: list[discord.Role]) -> list[str]:
    """Format one role collection for the owner-only diagnostic output."""

    if not roles:
        return ["- Aucun"]

    return [
        f"- {role.name} (`{role.id}`)"
        for role in roles
    ]


def create_roles_group(
    role_discovery_service: RoleDiscoveryService,
    report_service: ReportService,
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
            hierarchy = await role_discovery_service.get_hierarchy(
                interaction.guild,
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

        lines = [
            f"**Rôle de l'application :** {hierarchy.bot_role.name} (`{hierarchy.bot_role.id}`)",
            "",
            f"**Rôles de confiance ({len(hierarchy.trusted_roles)})**",
            *_format_roles(hierarchy.trusted_roles),
            "",
            f"**Rôles techniquement manipulables ({len(hierarchy.manageable_roles)})**",
            *_format_roles(hierarchy.manageable_roles),
            "",
            f"**Rôles non manipulables ({len(hierarchy.unmanageable_roles)})**",
            *_format_roles(hierarchy.unmanageable_roles),
            "",
            "Ce scan décrit uniquement la hiérarchie Discord. L'éligibilité d'un rôle pour un workflow est calculée séparément à partir de la configuration persistée.",
        ]

        await interaction.followup.send(
            "\n".join(lines),
            ephemeral=True,
        )

    return roles_group
