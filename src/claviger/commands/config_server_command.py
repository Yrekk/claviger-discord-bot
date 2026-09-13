import logging

import discord
from discord import app_commands

from claviger.database.status import DatabaseState
from claviger.models.admin_configuration_coordination_model import (
    AdminConfigurationCoordinationResult,
)
from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
)
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)

logger = logging.getLogger(__name__)


def _build_config_server_message(
    result: AdminConfigurationCoordinationResult,
) -> str:
    """Build one human-readable ADMIN configuration result."""

    decision = result.reconciliation.decision

    if decision == AdminConfigurationReconciliationDecision.KEEP:
        return "Configuration du serveur valide. Aucun changement n'était nécessaire."

    if decision == AdminConfigurationReconciliationDecision.CREATE:
        return (
            "Configuration du serveur créée avec succès : "
            "la structure ADMIN privée a été créée et son routage "
            "a été enregistré."
        )

    if decision == AdminConfigurationReconciliationDecision.COMPLETE:
        if result.configuration_after is None:
            return (
                "La structure ADMIN a été complétée, mais le routage "
                "activité / erreurs doit encore être sélectionné "
                "explicitement avant son enregistrement."
            )

        if result.configuration_updated:
            return (
                "La structure ADMIN a été réparée ou complétée et "
                "le routage persistant a été mis à jour."
            )

        if result.provisioning.changed:
            return (
                "La structure ADMIN a été réparée. "
                "Le routage persistant reste inchangé."
            )

        return (
            "La structure ADMIN a été vérifiée. "
            "Aucun changement persistant n'était nécessaire."
        )

    if decision == AdminConfigurationReconciliationDecision.IMPORT:
        return (
            "Une structure ADMIN compatible existe déjà. "
            "Aucun changement n'a été appliqué : les salons de commandes, "
            "d'activité et d'erreurs doivent être sélectionnés explicitement "
            "avant l'import."
        )

    if decision == AdminConfigurationReconciliationDecision.NEEDS_CHOICE:
        return (
            "La configuration nécessite un choix explicite entre plusieurs "
            "structures ADMIN possibles, ou la configuration persistante "
            "ne correspond plus à Discord. Aucun changement n'a été appliqué."
        )

    raise RuntimeError(f"Unsupported ADMIN reconciliation decision: {decision!r}.")


def create_config_server_command(
    coordinator: AdminConfigurationCoordinatorService,
    *,
    admin_command_name: str,
    database_state: DatabaseState,
    database_ownership_bound: bool,
) -> app_commands.Command:
    """Create the guild ADMIN configuration command."""

    @app_commands.command(
        name="config-server",
        description="Configure la structure d'administration du serveur.",
    )
    async def config_server(
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

        if database_state != DatabaseState.READY:
            await interaction.response.send_message(
                (
                    "La configuration du serveur est indisponible tant que "
                    "la base de données n'est pas prête. "
                    f"Utilise `/{admin_command_name} database status` "
                    "pour connaître l'action nécessaire."
                ),
                ephemeral=True,
            )
            return

        if not database_ownership_bound:
            await interaction.response.send_message(
                (
                    "La base de données est prête mais n'est pas encore liée "
                    "à cette application. "
                    f"Utilise `/{admin_command_name} database bind`, puis "
                    f"`/{admin_command_name} restart` avant de configurer "
                    "le serveur."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            ephemeral=True,
        )

        try:
            result = await coordinator.configure(
                interaction.guild,
            )

        except Exception:
            logger.exception(
                "Échec de la configuration ADMIN du serveur %s.",
                interaction.guild.id,
            )

            await interaction.followup.send(
                (
                    "Échec de la configuration du serveur. "
                    "Aucune déduction automatique supplémentaire n'a été faite."
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            _build_config_server_message(
                result,
            ),
            ephemeral=True,
        )

    return config_server
