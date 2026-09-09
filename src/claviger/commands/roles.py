from collections.abc import Iterable

import discord
from discord import app_commands

from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.adult_access_classifier import (
    AdultAccessClassifier,
)
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService


def _extract_access_keys(
    roles: Iterable[discord.Role],
    *,
    prefix: str,
) -> tuple[str, ...]:
    """Extract adult-access catalog keys from Discord role names."""

    if not prefix:
        return ()

    return tuple(
        role.name[len(prefix) :].strip()
        for role in roles
        if role.name.startswith(prefix)
    )


def _format_access_role_name(
    prefix: str,
    access_key: str,
) -> str:
    """Rebuild the Discord role name represented by one access key."""

    return f"{prefix}{access_key}"


def create_roles_group(
    role_discovery_service: RoleDiscoveryService,
    policy_resolver: PolicyResolver,
    role_classifier: RoleClassifier,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's role administration command group."""

    adult_access_classifier = AdultAccessClassifier()

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

            unmanageable_access_roles = (
                [
                    role
                    for role in hierarchy.unmanageable_roles
                    if (
                        policy.adult_access_prefix
                        and role.name.startswith(
                            policy.adult_access_prefix,
                        )
                    )
                ]
                if policy.adult_access_prefix
                else []
            )

            all_access_roles = (
                *classification.access_roles,
                *unmanageable_access_roles,
            )

            access_keys = _extract_access_keys(
                all_access_roles,
                prefix=policy.adult_access_prefix,
            )

            adult_access_classification = adult_access_classifier.classify(
                access_keys,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="roles.scan.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du scan des rôles",
                    summary=("Claviger n'a pas pu analyser la hiérarchie des rôles."),
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
            f"- Préfixe intérêts membre : {policy.member_interest_prefix}",
            f"- Préfixe accès adulte : {policy.adult_access_prefix}",
            "",
            f"**Rôles de confiance ({len(hierarchy.trusted_roles)})**",
        ]

        if hierarchy.trusted_roles:
            lines.extend(f"- {role.name}" for role in hierarchy.trusted_roles)
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                f"**Rôle membre ({len(classification.member_roles)})**",
            ]
        )

        if classification.member_roles:
            lines.extend(f"- {role.name}" for role in classification.member_roles)
        else:
            lines.append("- Introuvable")

        lines.extend(
            [
                "",
                f"**Rôle adulte ({len(classification.adult_roles)})**",
            ]
        )

        if classification.adult_roles:
            lines.extend(f"- {role.name}" for role in classification.adult_roles)
        else:
            lines.append("- Introuvable")

        lines.extend(
            [
                "",
                f"**Intérêts membre ({len(classification.interest_roles)})**",
            ]
        )

        if classification.interest_roles:
            lines.extend(f"- {role.name}" for role in classification.interest_roles)
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes — Paires "
                    f"({len(adult_access_classification.pairs)})**"
                ),
            ]
        )

        if adult_access_classification.pairs:
            for pair in adult_access_classification.pairs:
                no_ai_name = _format_access_role_name(
                    policy.adult_access_prefix,
                    pair.no_ai_key,
                )

                ai_name = _format_access_role_name(
                    policy.adult_access_prefix,
                    pair.ai_key,
                )

                lines.append(f"- {pair.theme_key} : {no_ai_name} + {ai_name}")
        else:
            lines.append("- Aucune")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes — Solo "
                    f"({len(adult_access_classification.solo_keys)})**"
                ),
            ]
        )

        if adult_access_classification.solo_keys:
            lines.extend(
                (
                    "- "
                    + _format_access_role_name(
                        policy.adult_access_prefix,
                        access_key,
                    )
                )
                for access_key in adult_access_classification.solo_keys
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes — IA uniquement "
                    f"({len(adult_access_classification.ai_only_keys)})**"
                ),
            ]
        )

        if adult_access_classification.ai_only_keys:
            lines.extend(
                (
                    "- "
                    + _format_access_role_name(
                        policy.adult_access_prefix,
                        access_key,
                    )
                )
                for access_key in adult_access_classification.ai_only_keys
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes — No-IA sans paire "
                    f"({len(adult_access_classification.no_ai_only_keys)})**"
                ),
            ]
        )

        if adult_access_classification.no_ai_only_keys:
            lines.extend(
                (
                    "- "
                    + _format_access_role_name(
                        policy.adult_access_prefix,
                        access_key,
                    )
                )
                for access_key in adult_access_classification.no_ai_only_keys
            )
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Accès adultes non manipulables "
                    f"({len(unmanageable_access_roles)})**"
                ),
            ]
        )

        if unmanageable_access_roles:
            lines.extend(f"- {role.name}" for role in unmanageable_access_roles)
        else:
            lines.append("- Aucun")

        lines.extend(
            [
                "",
                (
                    "**Clés d'accès adultes invalides "
                    f"({len(adult_access_classification.invalid_keys)})**"
                ),
            ]
        )

        if adult_access_classification.invalid_keys:
            lines.extend(
                (
                    "- "
                    + _format_access_role_name(
                        policy.adult_access_prefix,
                        access_key,
                    )
                )
                for access_key in adult_access_classification.invalid_keys
            )
        else:
            lines.append("- Aucune")

        lines.extend(
            [
                "",
                (
                    "**Clés d'accès adultes dupliquées "
                    f"({len(adult_access_classification.duplicate_keys)})**"
                ),
            ]
        )

        if adult_access_classification.duplicate_keys:
            lines.extend(
                (
                    "- "
                    + _format_access_role_name(
                        policy.adult_access_prefix,
                        access_key,
                    )
                )
                for access_key in adult_access_classification.duplicate_keys
            )
        else:
            lines.append("- Aucune")

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
            lines.extend(f"- {role.name}" for role in classification.unmanaged_roles)
        else:
            lines.append("- Aucun")

        anomalies: list[str] = []

        if len(classification.member_roles) == 0:
            anomalies.append(f'Rôle membre "{policy.member_role_name}" introuvable.')

        elif len(classification.member_roles) > 1:
            anomalies.append(f'Plusieurs rôles "{policy.member_role_name}" détectés.')

        if policy.adult_access_enabled:
            if len(classification.adult_roles) == 0:
                anomalies.append(f'Rôle adulte "{policy.adult_role_name}" introuvable.')

            elif len(classification.adult_roles) > 1:
                anomalies.append(
                    f'Plusieurs rôles "{policy.adult_role_name}" détectés.'
                )

            if not all_access_roles:
                anomalies.append(
                    (
                        "Aucun rôle d'accès adulte correspondant "
                        f'au préfixe "{policy.adult_access_prefix}" détecté.'
                    )
                )

            for access_key in adult_access_classification.no_ai_only_keys:
                role_name = _format_access_role_name(
                    policy.adult_access_prefix,
                    access_key,
                )

                anomalies.append((f'Accès no-IA sans variante IA : "{role_name}".'))

            for access_key in adult_access_classification.invalid_keys:
                role_name = _format_access_role_name(
                    policy.adult_access_prefix,
                    access_key,
                )

                anomalies.append(f'Clé d\'accès adulte invalide : "{role_name}".')

            for access_key in adult_access_classification.duplicate_keys:
                role_name = _format_access_role_name(
                    policy.adult_access_prefix,
                    access_key,
                )

                anomalies.append(f'Clé d\'accès adulte dupliquée : "{role_name}".')

            for role in unmanageable_access_roles:
                anomalies.append(
                    f'Rôle d\'accès adulte non manipulable : "{role.name}".'
                )

        lines.extend(
            [
                "",
                f"**Anomalies ({len(anomalies)})**",
            ]
        )

        if anomalies:
            lines.extend(f"- {anomaly}" for anomaly in anomalies)
        else:
            lines.append("- Aucune")

        await interaction.followup.send(
            "\n".join(lines),
            ephemeral=True,
        )

    return roles_group
