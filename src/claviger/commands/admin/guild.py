import discord
from discord import app_commands

from claviger.database.status import DatabaseState, DatabaseStatusService
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.guild_policy_bootstrap import (
    GuildAlreadyConfiguredError,
    GuildBootstrapNotAllowedError,
    GuildPolicyBootstrapService,
)


def create_guild_group(
    guild_policy_bootstrap_service: GuildPolicyBootstrapService,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's guild administration command group."""

    guild_group = app_commands.Group(
        name="guild",
        description="Configuration du serveur Discord.",
    )

    @guild_group.command(
        name="bootstrap",
        description="Initialise la configuration persistante du serveur.",
    )
    async def guild_bootstrap(
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
                        "d'initialiser la configuration du serveur."
                    ),
                    ephemeral=True,
                )
                return

            overrides = await guild_policy_bootstrap_service.bootstrap(
                interaction.guild.id,
            )

        except GuildAlreadyConfiguredError:
            await interaction.followup.send(
                "Ce serveur possède déjà une configuration persistante.",
                ephemeral=True,
            )
            return

        except GuildBootstrapNotAllowedError:
            await interaction.followup.send(
                (
                    "Le bootstrap initial est réservé au serveur "
                    "de secours configuré pour cette instance."
                ),
                ephemeral=True,
            )
            return

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="guild.bootstrap.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du bootstrap du serveur",
                    summary=(
                        "Claviger n'a pas pu créer la configuration "
                        "persistante du serveur."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Échec de l'initialisation de la configuration du serveur.",
                ephemeral=True,
            )
            return

        await report_service.emit(
            ReportEvent(
                event_type="guild.bootstrap.success",
                severity=ReportSeverity.INFO,
                title="Configuration du serveur initialisée",
                summary=(
                    "La configuration persistante du serveur a été créée avec succès."
                ),
                details=(
                    f"Rôle membre : {overrides.member_role_name}\n"
                    f"Rôle adulte : {overrides.adult_role_name}\n"
                    f"Préfixe intérêts : {overrides.member_interest_prefix}\n"
                    f"Préfixe accès adulte : {overrides.adult_access_prefix}"
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            "Configuration persistante du serveur initialisée avec succès.",
            ephemeral=True,
        )

    return guild_group
