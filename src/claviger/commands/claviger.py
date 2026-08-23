import discord
from discord import app_commands

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.event import (
    ReportEvent,
    ReportSeverity,
)
from claviger.reporting.service import ReportService
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService


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
            f"- Préfixe d'accès : {policy.access_role_prefix}",
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
                f"**Rôles d'accès ({len(classification.access_roles)})**",
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
                        "Aucun rôle d'accès correspondant au préfixe "
                        f'"{policy.access_role_prefix}" détecté.'
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

    return claviger_group