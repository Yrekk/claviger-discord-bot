import discord

from claviger.models.runtime.guild_role_diagnostic_model import (
    GuildRoleDiagnosticResult,
    RolePatternAnomaly,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService


class GuildRoleDiagnosticService:
    """Classify live roles against persisted generic workflow configuration."""

    def __init__(
        self,
        *,
        role_discovery_service: RoleDiscoveryService,
        role_channel_discovery_service: RoleChannelDiscoveryService,
        workflow_repository: WorkflowDefinitionRepository,
        catalog_entry_repository: CatalogEntryRepository,
        ai_repository: GuildAIConfigurationRepository,
    ) -> None:
        self.role_discovery_service = role_discovery_service
        self.role_channel_discovery_service = role_channel_discovery_service
        self.workflow_repository = workflow_repository
        self.catalog_entry_repository = catalog_entry_repository
        self.ai_repository = ai_repository

    async def inspect(
        self,
        guild: discord.Guild,
    ) -> GuildRoleDiagnosticResult:
        """Return workflow-aware role diagnostics without mutating Discord or SQLite."""

        hierarchy = await self.role_discovery_service.get_hierarchy(
            guild,
        )
        snapshot = self.role_channel_discovery_service.build_snapshot(
            guild,
        )
        workflows = await self.workflow_repository.list_for_guild(
            guild.id,
        )
        ai_configuration = await self.ai_repository.get(
            guild.id,
        )

        roles_by_id = {
            role.id: role
            for role in guild.roles
        }
        channels_by_id = {
            channel.channel_id: channel.channel_name
            for channel in snapshot.channels
        }

        primary_role_ids = {
            workflow.primary_role_id
            for workflow in workflows
            if workflow.primary_role_id is not None
        }

        configured_target_role_ids: set[int] = set()
        prefix_bindings: list[tuple[str, str]] = []
        seen_catalogs: set[str] = set()

        for workflow in workflows:
            for binding in workflow.catalogs:
                catalog = binding.catalog

                if not binding.enabled or not catalog.enabled:
                    continue

                prefix_bindings.append(
                    (
                        catalog.role_prefix,
                        f"{workflow.title} / {catalog.display_name}",
                    )
                )

                if catalog.catalog_key in seen_catalogs:
                    continue

                seen_catalogs.add(
                    catalog.catalog_key,
                )
                entries = await self.catalog_entry_repository.list_for_catalog(
                    guild_id=guild.id,
                    catalog_key=catalog.catalog_key,
                )
                configured_target_role_ids.update(
                    target.role_id
                    for entry in entries
                    for target in entry.targets
                )

        ai_role_id = (
            ai_configuration.ai_role_id
            if ai_configuration is not None
            else None
        )
        ai_role = (
            roles_by_id.get(
                ai_role_id,
            )
            if ai_role_id is not None
            else None
        )

        workflow_primary_role_names = tuple(
            sorted(
                {
                    roles_by_id[role_id].name
                    for role_id in primary_role_ids
                    if role_id in roles_by_id
                },
                key=str.casefold,
            )
        )

        configured_catalog_role_names = tuple(
            sorted(
                {
                    roles_by_id[role_id].name
                    for role_id in configured_target_role_ids
                    if role_id in roles_by_id
                },
                key=str.casefold,
            )
        )

        pattern_role_ids: set[int] = set()
        anomalies: list[RolePatternAnomaly] = []

        for role_snapshot in snapshot.roles:
            matching_bindings = tuple(
                (
                    prefix,
                    label,
                )
                for prefix, label in prefix_bindings
                if role_snapshot.role_name.startswith(prefix)
            )

            if not matching_bindings:
                continue

            matches = tuple(
                label
                for _, label in matching_bindings
            )
            matched_prefixes = {
                prefix
                for prefix, _ in matching_bindings
            }

            pattern_role_ids.add(
                role_snapshot.role_id,
            )
            reasons: list[str] = []

            if len(matched_prefixes) > 1:
                reasons.append(
                    "correspond à plusieurs patterns de workflow"
                )

            if any(
                role_snapshot.role_name == prefix
                for prefix in matched_prefixes
            ):
                reasons.append(
                    "pattern sans clé d'entrée"
                )

            if not role_snapshot.role_manageable:
                reasons.append(
                    "rôle non manipulable par l'application"
                )

            channel_count = len(
                role_snapshot.explicit_channel_ids,
            )

            if channel_count == 0:
                reasons.append(
                    "aucun salon/forum avec visibilité explicite"
                )
            elif channel_count > 1:
                reasons.append(
                    "plusieurs salons/forums avec visibilité explicite"
                )

            if role_snapshot.role_id not in configured_target_role_ids:
                reasons.append(
                    "absent des targets catalogue en BDD"
                )

            if not reasons:
                continue

            anomalies.append(
                RolePatternAnomaly(
                    role_name=role_snapshot.role_name,
                    workflow_labels=tuple(
                        sorted(
                            set(matches),
                            key=str.casefold,
                        )
                    ),
                    channel_names=tuple(
                        sorted(
                            (
                                channels_by_id[channel_id]
                                for channel_id in role_snapshot.explicit_channel_ids
                                if channel_id in channels_by_id
                            ),
                            key=str.casefold,
                        )
                    ),
                    reasons=tuple(
                        reasons,
                    ),
                )
            )

        configured_role_ids = (
            primary_role_ids
            | configured_target_role_ids
            | (
                {
                    ai_role_id,
                }
                if ai_role_id is not None
                else set()
            )
        )

        unconfigured_manageable_role_names = tuple(
            sorted(
                (
                    role.name
                    for role in hierarchy.manageable_roles
                    if role.id not in configured_role_ids
                    and role.id not in pattern_role_ids
                ),
                key=str.casefold,
            )
        )

        unmanageable_role_names = tuple(
            sorted(
                {
                    role.name
                    for role in hierarchy.unmanageable_roles
                },
                key=str.casefold,
            )
        )

        return GuildRoleDiagnosticResult(
            bot_role_name=hierarchy.bot_role.name,
            ai_enabled=(
                ai_configuration.ai_enabled
                if ai_configuration is not None
                else None
            ),
            ai_role_name=ai_role.name if ai_role is not None else None,
            ai_role_missing=ai_role_id is not None and ai_role is None,
            workflow_primary_role_names=workflow_primary_role_names,
            configured_catalog_role_names=configured_catalog_role_names,
            unconfigured_manageable_role_names=(
                unconfigured_manageable_role_names
            ),
            unmanageable_role_names=unmanageable_role_names,
            pattern_anomalies=tuple(
                sorted(
                    anomalies,
                    key=lambda anomaly: anomaly.role_name.casefold(),
                )
            ),
        )
