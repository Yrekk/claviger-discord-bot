import discord
from discord import app_commands

from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService


def create_report_group(
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's reporting command group."""

    report_group = app_commands.Group(
        name="report",
        description="Diagnostic du système de reporting de Claviger.",
    )

    @report_group.command(
        name="test",
        description="Teste le système de reporting administratif.",
    )
    async def test_reporting(
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

        await report_service.emit(
            ReportEvent(
                event_type="report.test",
                severity=ReportSeverity.INFO,
                title="Test du système de reporting",
                summary=(
                    "Le système de reporting de Claviger a reçu un événement de test."
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            ("Rapport de test émis. Vérifie le forum administratif."),
            ephemeral=True,
        )

    return report_group
