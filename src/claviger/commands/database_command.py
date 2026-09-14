import logging

import discord
from discord import app_commands

from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.ui.admin_configuration_view import AdminConfigurationStartView

logger = logging.getLogger(__name__)


def _format_database_status(
    status: DatabaseStatus,
) -> str:
    """Format a database status for an administrative Discord response."""

    state_labels = {
        DatabaseState.MISSING: "Absente",
        DatabaseState.UNINITIALIZED: "Non initialisée",
        DatabaseState.READY: "Prête",
        DatabaseState.MIGRATION_REQUIRED: "Migration requise",
        DatabaseState.TOO_NEW: "Version trop récente",
        DatabaseState.UNAVAILABLE: "Indisponible",
    }

    recommendations = {
        DatabaseState.MISSING: "Initialiser manuellement la base de données.",
        DatabaseState.UNINITIALIZED: ("Initialiser le schéma de la base de données."),
        DatabaseState.READY: "Aucune action nécessaire.",
        DatabaseState.MIGRATION_REQUIRED: ("Exécuter manuellement les migrations."),
        DatabaseState.TOO_NEW: (
            "Ne pas modifier la base. Vérifier la version de Claviger."
        ),
        DatabaseState.UNAVAILABLE: (
            "Vérifier le fichier, les permissions et l'environnement d'exécution."
        ),
    }

    current_version = (
        str(status.current_version) if status.current_version is not None else "N/A"
    )

    return "\n".join(
        [
            "**Base de données Claviger**",
            "",
            f"- État : **{state_labels[status.state]}**",
            f"- Version actuelle : `{current_version}`",
            f"- Version attendue : `{status.target_version}`",
            "",
            (f"**Action recommandée :** {recommendations[status.state]}"),
        ]
    )


async def _send_database_ready_guidance(
    interaction: discord.Interaction,
    *,
    coordinator: AdminConfigurationCoordinatorService,
    admin_command_name: str,
    success_message: str,
) -> None:
    """Guide one guild from DB readiness to ADMIN readiness without extra restart."""

    if interaction.guild is None:
        raise RuntimeError("Database readiness guidance requires a guild interaction.")

    try:
        configuration = await coordinator.get_persisted_configuration(
            interaction.guild.id,
        )

    except Exception:
        logger.exception(
            "Unable to inspect ADMIN configuration after database maintenance "
            "for guild %s.",
            interaction.guild.id,
        )

        await interaction.followup.send(
            (
                f"{success_message}\n\n"
                "⚠️ La configuration ADMIN de ce serveur n'a pas pu être "
                "vérifiée automatiquement. "
                f"Utilise `/{admin_command_name} restart`, puis "
                f"`/{admin_command_name} config-server`."
            ),
            ephemeral=True,
        )
        return

    if configuration is None or not configuration.is_complete:
        await interaction.followup.send(
            (
                f"{success_message}\n\n"
                "⚙️ **La configuration ADMIN de ce serveur doit maintenant "
                "être terminée.**\n"
                "Configure les destinations administratives avant de redémarrer. "
                "Cela évite un redémarrage intermédiaire inutile."
            ),
            ephemeral=True,
            view=AdminConfigurationStartView(
                coordinator=coordinator,
                actor_id=interaction.user.id,
                guild_id=interaction.guild.id,
                admin_command_name=admin_command_name,
            ),
        )
        return

    await interaction.followup.send(
        (
            f"{success_message} "
            f"Utilise `/{admin_command_name} restart` pour activer "
            "les commandes dépendantes de la base."
        ),
        ephemeral=True,
    )


def create_database_group(
    database_schema: DatabaseSchema,
    database_status_service: DatabaseStatusService,
    database_ownership_service: DatabaseOwnershipService,
    report_service: ReportService,
    *,
    admin_configuration_coordinator_service: AdminConfigurationCoordinatorService,
    application_id: int,
    admin_command_name: str,
) -> app_commands.Group:
    """Create the database administration command group."""

    database_group = app_commands.Group(
        name="database",
        description="Diagnostic et maintenance de la base de données.",
    )

    @database_group.command(
        name="status",
        description="Affiche l'état de la base de données de Claviger.",
    )
    async def database_status(
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

        except Exception as error:
            await interaction.followup.send(
                "Impossible de déterminer l'état de la base de données.",
                ephemeral=True,
            )

            await report_service.emit(
                ReportEvent(
                    event_type="database.status.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du diagnostic de la base de données",
                    summary=(
                        "Claviger n'a pas pu déterminer l'état de sa base de données."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )
            return

        await interaction.followup.send(
            _format_database_status(
                status,
            ),
            ephemeral=True,
        )

    @database_group.command(
        name="initialize",
        description="Initialise explicitement la base de données de Claviger.",
    )
    async def database_initialize(
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

            if status.state == DatabaseState.READY:
                await interaction.followup.send(
                    (
                        "La base de données est déjà initialisée. "
                        f"Utilise `/{admin_command_name} database bind` "
                        "si son application propriétaire doit être vérifiée."
                    ),
                    ephemeral=True,
                )
                return

            if status.state == DatabaseState.MIGRATION_REQUIRED:
                await interaction.followup.send(
                    (
                        "La base de données existe déjà mais nécessite "
                        f"une migration. Utilise `/{admin_command_name} "
                        "database migrate`."
                    ),
                    ephemeral=True,
                )
                return

            if status.state == DatabaseState.TOO_NEW:
                raise RuntimeError(
                    "La base de données utilise une version de schéma "
                    "plus récente que cette version de Claviger."
                )

            if status.state == DatabaseState.UNAVAILABLE:
                raise RuntimeError("La base de données est actuellement indisponible.")

            await database_schema.initialize()

            await database_ownership_service.bind(
                application_id,
            )

            final_status = await database_status_service.check()

            if final_status.state != DatabaseState.READY:
                raise RuntimeError(
                    (
                        "Database initialization completed but "
                        f"final state is {final_status.state.value}."
                    )
                )

        except Exception as error:
            await interaction.followup.send(
                "Échec de l'initialisation de la base de données.",
                ephemeral=True,
            )

            await report_service.emit(
                ReportEvent(
                    event_type="database.initialize.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de l'initialisation de la base de données",
                    summary=("Claviger n'a pas pu initialiser sa base de données."),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )
            return

        await _send_database_ready_guidance(
            interaction,
            coordinator=admin_configuration_coordinator_service,
            admin_command_name=admin_command_name,
            success_message=(
                "Base de données initialisée et liée à cette application. "
                f"Version du schéma : `{final_status.current_version}`."
            ),
        )

        await report_service.emit(
            ReportEvent(
                event_type="database.initialize.success",
                severity=ReportSeverity.INFO,
                title="Base de données initialisée",
                summary=(
                    "La base de données de Claviger a été initialisée avec succès."
                ),
                details=(
                    f"Schema version: {final_status.current_version}; "
                    f"application_id: {application_id}"
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

    @database_group.command(
        name="migrate",
        description="Migre explicitement la base de données de Claviger.",
    )
    async def database_migrate(
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

            if status.state == DatabaseState.READY:
                await interaction.followup.send(
                    (
                        "La base de données est déjà à jour. "
                        f"Utilise `/{admin_command_name} database bind` "
                        "si son application propriétaire doit être vérifiée."
                    ),
                    ephemeral=True,
                )
                return

            if status.state in (
                DatabaseState.MISSING,
                DatabaseState.UNINITIALIZED,
            ):
                await interaction.followup.send(
                    (
                        "La base de données n'est pas initialisée. "
                        f"Utilise `/{admin_command_name} database initialize`."
                    ),
                    ephemeral=True,
                )
                return

            if status.state == DatabaseState.TOO_NEW:
                raise RuntimeError(
                    "La base de données utilise une version de schéma "
                    "plus récente que cette version de Claviger."
                )

            if status.state == DatabaseState.UNAVAILABLE:
                raise RuntimeError("La base de données est actuellement indisponible.")

            if status.state != DatabaseState.MIGRATION_REQUIRED:
                raise RuntimeError(f"Unexpected database state: {status.state.value}.")

            previous_version = status.current_version

            await database_schema.migrate()

            await database_ownership_service.bind(
                application_id,
            )

            final_status = await database_status_service.check()

            if final_status.state != DatabaseState.READY:
                raise RuntimeError(
                    (
                        "Database migration completed but "
                        f"final state is {final_status.state.value}."
                    )
                )

        except Exception as error:
            await interaction.followup.send(
                "Échec de la migration de la base de données.",
                ephemeral=True,
            )

            await report_service.emit(
                ReportEvent(
                    event_type="database.migrate.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la migration de la base de données",
                    summary=("Claviger n'a pas pu migrer sa base de données."),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )
            return

        await _send_database_ready_guidance(
            interaction,
            coordinator=admin_configuration_coordinator_service,
            admin_command_name=admin_command_name,
            success_message=(
                "Base de données migrée et liée à cette application : "
                f"`{previous_version}` → `{final_status.current_version}`."
            ),
        )

        await report_service.emit(
            ReportEvent(
                event_type="database.migrate.success",
                severity=ReportSeverity.INFO,
                title="Base de données migrée",
                summary=("La base de données de Claviger a été migrée avec succès."),
                details=(
                    f"Schema version: {previous_version} "
                    f"-> {final_status.current_version}; "
                    f"application_id: {application_id}"
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

    @database_group.command(
        name="bind",
        description="Lie explicitement la base à l'application Discord actuelle.",
    )
    async def database_bind(
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
                        "La base de données doit être initialisée et à jour "
                        "avant de pouvoir être liée à une application."
                    ),
                    ephemeral=True,
                )
                return

            await database_ownership_service.bind(
                application_id,
            )

            owner_application_id = (
                await database_ownership_service.get_owner_application_id()
            )

            if owner_application_id != application_id:
                raise RuntimeError(
                    "Database ownership binding completed with an unexpected owner."
                )

        except Exception as error:
            await interaction.followup.send(
                "Échec de la liaison de la base de données.",
                ephemeral=True,
            )

            await report_service.emit(
                ReportEvent(
                    event_type="database.bind.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la liaison de la base de données",
                    summary=(
                        "Claviger n'a pas pu lier la base de données "
                        "à l'application Discord actuelle."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )
            return

        await _send_database_ready_guidance(
            interaction,
            coordinator=admin_configuration_coordinator_service,
            admin_command_name=admin_command_name,
            success_message="Base de données liée à cette application Discord.",
        )

        await report_service.emit(
            ReportEvent(
                event_type="database.bind.success",
                severity=ReportSeverity.INFO,
                title="Base de données liée",
                summary=(
                    "La base de données de Claviger est liée "
                    "à l'application Discord actuelle."
                ),
                details=f"application_id: {application_id}",
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

    return database_group
