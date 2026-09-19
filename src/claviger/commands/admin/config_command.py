import discord
from discord import app_commands

from claviger.commands.admin.diagnostic_output import send_ephemeral_diagnostic
from claviger.database.status import DatabaseState
from claviger.models.admin.admin_configuration_inspection_model import (
    AdminConfigurationInspectionResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
)
from claviger.models.runtime.guild_configuration_inspection_model import (
    GuildConfigurationInspectionResult,
)
from claviger.models.runtime.guild_policy_inspection_model import GuildPolicySource
from claviger.reporting.event import ReportEvent, ReportSeverity
from claviger.reporting.service import ReportService
from claviger.services.runtime.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)

_POLICY_SOURCE_LABELS = {
    GuildPolicySource.SAFE_DEFAULT: "SAFE_DEFAULT_POLICY",
    GuildPolicySource.SQLITE_OVERRIDES: "SAFE_DEFAULT_POLICY + overrides SQLite",
    GuildPolicySource.HISTORICAL_FALLBACK: "HISTORICAL_FALLBACK_POLICY",
    GuildPolicySource.SAFE_DATABASE_FALLBACK: "SAFE_DEFAULT_POLICY (fallback BDD)",
}


def _find_configured_category(
    inspection: AdminConfigurationInspectionResult,
) -> AdminCategoryCandidate | None:
    configuration = inspection.configuration

    if configuration is None:
        return None

    return next(
        (
            category
            for category in inspection.discovery.categories
            if category.category_id == configuration.category_id
        ),
        None,
    )


def _find_channel(
    category: AdminCategoryCandidate | None,
    channel_id: int | None,
) -> AdminChannelCandidate | None:
    if category is None or channel_id is None:
        return None

    return next(
        (
            channel
            for channel in category.channels
            if channel.channel_id == channel_id
        ),
        None,
    )


def _format_admin_category(
    category_id: int,
    category: AdminCategoryCandidate | None,
) -> str:
    if category is None:
        return f"❌ ID `{category_id}` introuvable sur Discord"

    issues: list[str] = []

    if not category.is_private:
        issues.append("visibilité non privée")

    if not category.bot_can_view:
        issues.append("application sans accès")

    status = "✅" if not issues else "⚠️"
    suffix = "" if not issues else " — " + ", ".join(issues)

    return f"{status} {category.category_name} (`{category.category_id}`){suffix}"


def _format_admin_channel(
    *,
    channel_id: int | None,
    category: AdminCategoryCandidate | None,
    expected_type: str,
) -> str:
    if channel_id is None:
        return "❌ non configuré en BDD"

    channel = _find_channel(
        category,
        channel_id,
    )

    if channel is None:
        return f"❌ ID `{channel_id}` introuvable dans la catégorie ADMIN"

    issues: list[str] = []

    if channel.channel_type != expected_type:
        issues.append(f"type `{channel.channel_type}` au lieu de `{expected_type}`")

    if not channel.is_private:
        issues.append("visible par @everyone")

    if not channel.bot_usable:
        issues.append("application sans accès utilisable")

    status = "✅" if not issues else "⚠️"
    suffix = "" if not issues else " — " + ", ".join(issues)

    return f"{status} #{channel.channel_name} (`{channel.channel_id}`){suffix}"


def _format_database_lines(
    result: GuildConfigurationInspectionResult,
) -> list[str]:
    status = result.database_status
    current_version = "—" if status.current_version is None else str(status.current_version)

    lines = [
        "**Base de données**",
        f"- État : `{status.state.value.upper()}`",
        f"- Schéma : `{current_version}` / cible `{status.target_version}`",
    ]

    if status.state != DatabaseState.READY:
        lines.append("- Ownership : ⏸ non évalué tant que la BDD n'est pas READY")
        return lines

    owner_application_id = result.database_owner_application_id

    if owner_application_id is None:
        lines.append("- Ownership : ❌ aucune application liée")
    elif result.database_owned_by_application:
        lines.append(
            "- Ownership : ✅ application courante "
            f"(`{result.application_id}`)"
        )
    else:
        lines.append(
            "- Ownership : ❌ autre application "
            f"(`{owner_application_id}`)"
        )

    return lines


def _format_admin_lines(
    result: GuildConfigurationInspectionResult,
) -> list[str]:
    inspection = result.admin

    if inspection is None:
        return [
            "**ADMIN**",
            "- État : ⏸ non évalué tant que la BDD n'est pas READY et correctement liée",
        ]

    configuration = inspection.configuration

    if configuration is None:
        return [
            "**ADMIN**",
            "- Persistance BDD : ❌ absente",
            f"- Réconciliation : `{inspection.reconciliation.decision.value.upper()}`",
            "- État : ❌ UNCONFIGURED",
        ]

    category = _find_configured_category(
        inspection,
    )

    if inspection.is_routing_ready:
        routing_state = "✅ READY"
    elif not configuration.is_complete:
        routing_state = "⚠️ INCOMPLETE"
    else:
        routing_state = "❌ DRIFT / RÉPARATION REQUISE"

    persistence_state = "✅ complète" if configuration.is_complete else "⚠️ incomplète"

    return [
        "**ADMIN**",
        f"- Persistance BDD : {persistence_state}",
        "- Catégorie : "
        + _format_admin_category(
            configuration.category_id,
            category,
        ),
        "- Salon de commandes : "
        + _format_admin_channel(
            channel_id=configuration.command_channel_id,
            category=category,
            expected_type="text",
        ),
        "- Forum activity : "
        + _format_admin_channel(
            channel_id=configuration.activity_forum_id,
            category=category,
            expected_type="forum",
        ),
        "- Forum error : "
        + _format_admin_channel(
            channel_id=configuration.error_forum_id,
            category=category,
            expected_type="forum",
        ),
        f"- Réconciliation : `{inspection.reconciliation.decision.value.upper()}`",
        f"- État : {routing_state}",
    ]


def _format_policy_lines(
    result: GuildConfigurationInspectionResult,
) -> list[str]:
    inspection = result.policy

    if inspection is None:
        return [
            "**Policy effective**",
            "- ⏸ non évaluée tant que la BDD n'est pas READY et correctement liée",
        ]

    policy = inspection.effective
    source = _POLICY_SOURCE_LABELS[inspection.source]
    override_count = inspection.persisted_override_count
    override_label = "aucun" if override_count == 0 else str(override_count)

    return [
        "**Policy effective — compatibilité actuelle**",
        f"- Source : `{source}`",
        f"- Overrides persistés : {override_label}",
        f"- `member_role_name` : {policy.member_role_name}",
        f"- `adult_role_name` : {policy.adult_role_name}",
        f"- `member_interest_prefix` : {policy.member_interest_prefix}",
        f"- `adult_access_prefix` : {policy.adult_access_prefix}",
        f"- `salutations_channel_name` : {policy.salutations_channel_name}",
        f"- `adult_access_channel_name` : {policy.adult_access_channel_name}",
        "- `role_management_enabled` : "
        + ("true" if policy.role_management_enabled else "false"),
        "- `adult_access_enabled` : "
        + ("true" if policy.adult_access_enabled else "false"),
    ]


def _format_metrics_lines(
    result: GuildConfigurationInspectionResult,
) -> list[str]:
    metrics = result.metrics

    if metrics is None:
        return [
            "**Configuration déclarative**",
            "- ⏸ non évaluée tant que la BDD n'est pas READY et correctement liée",
        ]

    return [
        "**Configuration déclarative**",
        f"- Workflows activés : {metrics.workflow_count}",
        f"- Catalogues activés : {metrics.catalog_count}",
        f"- Contextes partagés activés : {metrics.context_count}",
    ]


def _format_ai_lines(
    result: GuildConfigurationInspectionResult,
    guild: discord.Guild,
) -> list[str]:
    configuration = result.ai_configuration

    if result.workflows is None:
        return []

    if configuration is None:
        state = "non configurée"
        role_label = "aucun"
    elif configuration.ai_enabled is None:
        state = "non configurée"
        role_label = "aucun"
    elif configuration.ai_enabled is False:
        state = "désactivée"
        role = (
            guild.get_role(
                configuration.ai_role_id,
            )
            if configuration.ai_role_id is not None
            else None
        )
        if configuration.ai_role_id is None:
            role_label = "aucun"
        elif role is None:
            role_label = "⚠️ rôle conservé introuvable"
        else:
            role_label = f"{role.name} (conservé)"
    else:
        state = "activée"
        role = (
            guild.get_role(
                configuration.ai_role_id,
            )
            if configuration.ai_role_id is not None
            else None
        )

        if configuration.ai_role_id is None:
            role_label = "❌ aucun rôle configuré"
        elif role is None:
            role_label = "❌ rôle configuré introuvable"
        else:
            role_label = role.name

    owner_key = result.ai_questionnaire_owner_workflow_key
    owner_label = "aucun"

    if owner_key is not None:
        owner_workflow = next(
            (
                workflow
                for workflow in result.workflows
                if workflow.workflow_key == owner_key
            ),
            None,
        )

        owner_label = (
            f"/{owner_workflow.command_name}"
            if owner_workflow is not None
            else f"{owner_key} (workflow introuvable)"
        )

    return [
        "**IA globale**",
        f"- État : {state}",
        f"- Rôle IA : {role_label}",
        f"- Workflow propriétaire de la question IA : {owner_label}",
    ]


def _format_workflow_lines(
    result: GuildConfigurationInspectionResult,
) -> list[str]:
    workflows = result.workflows
    discovery = result.workflow_discovery

    if workflows is None:
        return []

    categories_by_id = (
        {
            category.category_id: category.category_name
            for category in discovery.categories
        }
        if discovery is not None
        else {}
    )

    lines = [
        f"**Workflows configurés ({len(workflows)})**",
    ]

    if not workflows:
        lines.append(
            "- Aucun"
        )

    for workflow in workflows:
        category_name = (
            categories_by_id.get(
                workflow.category_id,
            )
            if workflow.category_id is not None
            else None
        )

        workflow_state = (
            "✅ actif"
            if workflow.enabled
            else "⏸ désactivé"
        )

        lines.extend(
            [
                "=============",
                (
                    f"- **{workflow.title}** — /{workflow.command_name} "
                    f"— {workflow_state}"
                ),
                (
                    f"  Catégorie : {category_name}"
                    if category_name is not None
                    else "  Catégorie : ❌ absente ou non configurée"
                ),
            ]
        )

    if discovery is None:
        return lines

    unconfigured_candidates = []

    for candidate in discovery.workflow_candidates:
        protected_ids = {
            channel.channel_id
            for channel in candidate.protected_channels
        }
        interactive_ids = {
            channel.channel_id
            for channel in candidate.interactive_channels
        }

        configured = any(
            workflow.category_id == candidate.category.category_id
            and workflow.management_channel_id in protected_ids
            and bool(workflow.channel_ids)
            and set(workflow.channel_ids).issubset(
                interactive_ids,
            )
            for workflow in workflows
        )

        if not configured:
            unconfigured_candidates.append(
                candidate,
            )

    lines.extend(
        [
            "",
            (
                "**Structures Discord détectées mais non configurées "
                f"({len(unconfigured_candidates)})**"
            ),
        ]
    )

    if not unconfigured_candidates:
        lines.append(
            "- Aucune"
        )
        return lines

    for candidate in unconfigured_candidates:
        protected = ", ".join(
            f"#{channel.channel_name}"
            for channel in candidate.protected_channels
        )
        interactive = ", ".join(
            f"#{channel.channel_name}"
            for channel in candidate.interactive_channels
        )

        lines.extend(
            [
                "=============",
                f"- Catégorie : {candidate.category.category_name}",
                f"  Salons protégés : {protected or 'aucun'}",
                f"  Salons interactifs : {interactive or 'aucun'}",
            ]
        )

    return lines


def create_config_group(
    inspection_service: GuildConfigurationInspectionService,
    report_service: ReportService,
    *,
    application_name: str,
    application_id: int,
) -> app_commands.Group:
    """Create the application's read-only configuration diagnostic group."""

    config_group = app_commands.Group(
        name="config",
        description=f"Diagnostic de configuration de {application_name}.",
    )

    @config_group.command(
        name="scan",
        description="Inspecte la configuration persistée et l'état Discord réel.",
    )
    async def scan_configuration(
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
            result = await inspection_service.inspect(
                interaction.guild,
                application_id=application_id,
            )

        except Exception as error:
            await report_service.emit(
                ReportEvent(
                    event_type="config.scan.failed",
                    severity=ReportSeverity.ERROR,
                    title="Échec du diagnostic de configuration",
                    summary=(
                        f"{application_name} n'a pas pu inspecter "
                        "la configuration de ce serveur."
                    ),
                    details=str(error),
                    guild_id=interaction.guild.id,
                    guild_label=interaction.guild.name,
                    actor_id=interaction.user.id,
                    actor_label=interaction.user.display_name,
                )
            )

            await interaction.followup.send(
                f"Impossible d'inspecter la configuration : {error}",
                ephemeral=True,
            )
            return

        sections = [
            [
                f"**Application — {application_name}**",
                f"- Application ID : `{application_id}`",
                f"- Serveur : {interaction.guild.name} (`{interaction.guild.id}`)",
            ],
            _format_database_lines(result),
            _format_admin_lines(result),
            _format_policy_lines(result),
            _format_metrics_lines(result),
            _format_ai_lines(
                result,
                interaction.guild,
            ),
            _format_workflow_lines(
                result,
            ),
        ]

        lines: list[str] = []

        for section in sections:
            if not section:
                continue

            if lines:
                lines.append(
                    "",
                )

            lines.extend(
                section,
            )

        await send_ephemeral_diagnostic(
            interaction,
            lines,
        )

    return config_group
