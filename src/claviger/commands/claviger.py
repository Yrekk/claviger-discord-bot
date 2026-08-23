import discord
from discord import app_commands

from claviger.policies.policy_resolver import PolicyResolver
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService


def create_claviger_group(
    role_discovery_service: RoleDiscoveryService,
    policy_resolver: PolicyResolver,
    role_classifier: RoleClassifier,
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

    return claviger_group