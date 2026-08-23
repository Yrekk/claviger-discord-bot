import discord
from discord import app_commands

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.database.schema import DatabaseSchema

from claviger.policies.policy_resolver import PolicyResolver

from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.service import ReportService

from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService
from claviger.services.guild_policy_bootstrap import (
    GuildAlreadyConfiguredError,
    GuildBootstrapNotAllowedError,
    GuildPolicyBootstrapService,
)


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
        DatabaseState.MISSING: (
            "Initialiser manuellement la base de données."
        ),
        DatabaseState.UNINITIALIZED: (
            "Initialiser le schéma de la base de données."
        ),
        DatabaseState.READY: (
            "Aucune action nécessaire."
        ),
        DatabaseState.MIGRATION_REQUIRED: (
            "Exécuter manuellement les migrations."
        ),
        DatabaseState.TOO_NEW: (
            "Ne pas modifier la base. "
            "Vérifier la version de Claviger."
        ),
        DatabaseState.UNAVAILABLE: (
            "Vérifier le fichier, les permissions "
            "et l'environnement d'exécution."
        ),
    }

    current_version = (
        str(status.current_version)
        if status.current_version is not None
        else "N/A"
    )

    return "\n".join(
        [
            "**Base de données Claviger**",
            "",
            f"- État : **{state_labels[status.state]}**",
            f"- Version actuelle : `{current_version}`",
            f"- Version attendue : `{status.target_version}`",
            "",
            (
                "**Action recommandée :** "
                f"{recommendations[status.state]}"
            ),
        ]
    )


def create_claviger_group(
    role_discovery_service: RoleDiscoveryService,
    policy_resolver: PolicyResolver,
    role_classifier: RoleClassifier,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService,
    database_schema: DatabaseSchema,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's administrative command group."""

    claviger_group = app_commands.Group(
        name="claviger",
        description="Commandes d'administration de Claviger.",
    )

    roles_group = app_commands.Group(
        name="roles",
        description="Analyse et gestion des rôles Discord.",
    )

    report_group = app_commands.Group(
        name="report",
        description="Diagnostic du système de reporting de Claviger.",
    )

    database_group = app_commands.Group(
        name="database",
        description="Diagnostic et maintenance de la base de données.",
    )

    guild_group = app_commands.Group(
    name="guild",
    description="Configuration du serveur Discord.",
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
                    "Le système de reporting de Claviger "
                    "a reçu un événement de test."
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            (
                "Rapport de test émis. "
                "Vérifie le forum administratif."
            ),
            ephemeral=True,
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
            await report_service.emit(
                ReportEvent(
                    event_type="database.status.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du diagnostic de la base de données",
                    summary=(
                        "Claviger n'a pas pu déterminer "
                        "l'état de sa base de données."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Impossible de déterminer l'état de la base de données.",
                ephemeral=True,
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
                    "La base de données est déjà initialisée et prête.",
                    ephemeral=True,
                )
                return

            if status.state == DatabaseState.MIGRATION_REQUIRED:
                await interaction.followup.send(
                    (
                        "La base de données existe déjà mais nécessite "
                        "une migration. Utilise `/claviger database migrate`."
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
                raise RuntimeError(
                    "La base de données est actuellement indisponible."
                )

            await database_schema.initialize()

            final_status = await database_status_service.check()

            if final_status.state != DatabaseState.READY:
                raise RuntimeError(
                    (
                        "Database initialization completed but "
                        f"final state is {final_status.state.value}."
                    )
                )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="database.initialize.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de l'initialisation de la base de données",
                    summary=(
                        "Claviger n'a pas pu initialiser "
                        "sa base de données."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Échec de l'initialisation de la base de données.",
                ephemeral=True,
            )
            return

        await report_service.emit(
            ReportEvent(
                event_type="database.initialize.success",
                severity=ReportSeverity.INFO,
                title="Base de données initialisée",
                summary=(
                    "La base de données de Claviger "
                    "a été initialisée avec succès."
                ),
                details=(
                    f"Schema version: {final_status.current_version}"
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            (
                "Base de données initialisée avec succès. "
                f"Version du schéma : `{final_status.current_version}`."
            ),
            ephemeral=True,
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
                    "La base de données est déjà à jour.",
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
                        "Utilise `/claviger database initialize`."
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
                raise RuntimeError(
                    "La base de données est actuellement indisponible."
                )

            if status.state != DatabaseState.MIGRATION_REQUIRED:
                raise RuntimeError(
                    f"Unexpected database state: {status.state.value}."
                )

            previous_version = status.current_version

            await database_schema.migrate()

            final_status = await database_status_service.check()

            if final_status.state != DatabaseState.READY:
                raise RuntimeError(
                    (
                        "Database migration completed but "
                        f"final state is {final_status.state.value}."
                    )
                )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="database.migrate.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec de la migration de la base de données",
                    summary=(
                        "Claviger n'a pas pu migrer "
                        "sa base de données."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                "Échec de la migration de la base de données.",
                ephemeral=True,
            )
            return

        await report_service.emit(
            ReportEvent(
                event_type="database.migrate.success",
                severity=ReportSeverity.INFO,
                title="Base de données migrée",
                summary=(
                    "La base de données de Claviger "
                    "a été migrée avec succès."
                ),
                details=(
                    f"Schema version: {previous_version} "
                    f"-> {final_status.current_version}"
                ),
                guild_id=interaction.guild.id,
                guild_label=interaction.guild.name,
                actor_id=interaction.user.id,
                actor_label=interaction.user.display_name,
            )
        )

        await interaction.followup.send(
            (
                "Base de données migrée avec succès : "
                f"`{previous_version}` → `{final_status.current_version}`."
            ),
            ephemeral=True,
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

        try:
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
                    "La configuration persistante du serveur "
                    "a été créée avec succès."
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
            (
                "Configuration persistante du serveur initialisée avec succès."
            ),
            ephemeral=True,
        )

    @roles_group.command(
        name="scan",
        description="Analyse la hiérarchie et la politique des rôles du serveur.",
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

            policy = await policy_resolver.resolve(
                interaction.guild.id,
            )

            classification = role_classifier.classify(
                hierarchy,
                policy,
            )

        except RuntimeError as error:
            await report_service.emit(
                ReportEvent(
                    event_type="roles.scan.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du scan des rôles",
                    summary=(
                        "Claviger n'a pas pu analyser "
                        "la hiérarchie des rôles."
                    ),
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
            f"**Rôle de Claviger :** {hierarchy.bot_role.name}",
            "",
            "**Policy effective**",
            (
                "- Gestion des rôles : "
                f"{'activée' if policy.role_management_enabled else 'désactivée'}"
            ),
            (
                "- Accès adulte : "
                f"{'activé' if policy.adult_access_enabled else 'désactivé'}"
            ),
            f"- Rôle membre attendu : {policy.member_role_name}",
            f"- Rôle adulte attendu : {policy.adult_role_name}",
            (
                "- Préfixe intérêts membre : "
                f"{policy.member_interest_prefix}"
            ),
            (
                "- Préfixe accès adulte : "
                f"{policy.adult_access_prefix}"
            ),
            "",
            f"**Rôles de confiance ({len(hierarchy.trusted_roles)})**",
        ]

        if hierarchy.trusted_roles:
            lines.extend(
                f"- {role.name}"
                for role in hierarchy.trusted_roles
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                f"**Rôle membre ({len(classification.member_roles)})**",
            ]
        )

        if classification.member_roles:
            lines.extend(
                f"- {role.name}"
                for role in classification.member_roles
            )
        else:
            lines.append("- Introuvable")

        lines.extend(
            [
                "",
                f"**Rôle adulte ({len(classification.adult_roles)})**",
            ]
        )

        if classification.adult_roles:
            lines.extend(
                f"- {role.name}"
                for role in classification.adult_roles
            )
        else:
            lines.append("- Introuvable")

        lines.extend(
            [
                "",
                (
                    "**Intérêts membre "
                    f"({len(classification.interest_roles)})**"
                ),
            ]
        )

        if classification.interest_roles:
            lines.extend(
                f"- {role.name}"
                for role in classification.interest_roles
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes "
                    f"({len(classification.access_roles)})**"
                ),
            ]
        )

        if classification.access_roles:
            lines.extend(
                f"- {role.name}"
                for role in classification.access_roles
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Autres rôles sous Claviger "
                    f"({len(classification.unmanaged_roles)})**"
                ),
            ]
        )

        if classification.unmanaged_roles:
            lines.extend(
                f"- {role.name}"
                for role in classification.unmanaged_roles
            )
        else:
            lines.append("- Aucun")

        anomalies: list[str] = []

        if len(classification.member_roles) == 0:
            anomalies.append(
                f'Rôle membre "{policy.member_role_name}" introuvable.'
            )

        elif len(classification.member_roles) > 1:
            anomalies.append(
                f'Plusieurs rôles "{policy.member_role_name}" détectés.'
            )

        if policy.adult_access_enabled:
            if len(classification.adult_roles) == 0:
                anomalies.append(
                    f'Rôle adulte "{policy.adult_role_name}" introuvable.'
                )

            elif len(classification.adult_roles) > 1:
                anomalies.append(
                    f'Plusieurs rôles "{policy.adult_role_name}" détectés.'
                )

            if not classification.access_roles:
                anomalies.append(
                    (
                        "Aucun rôle d'accès adulte correspondant "
                        f'au préfixe "{policy.adult_access_prefix}" détecté.'
                    )
                )

        lines.extend(
            [
                "",
                f"**Anomalies ({len(anomalies)})**",
            ]
        )

        if anomalies:
            lines.extend(
                f"- {anomaly}"
                for anomaly in anomalies
            )
        else:
            lines.append("- Aucune")

        await interaction.followup.send(
            "\n".join(lines),
            ephemeral=True,
        )

    claviger_group.add_command(
        roles_group,
    )

    claviger_group.add_command(
        report_group,
    )

    claviger_group.add_command(
        database_group,
    )
    claviger_group.add_command(
        guild_group,
    )

    return claviger_group