import discord

from claviger.models.runtime.workflow_catalog_diagnostic_model import (
    CatalogMetadataIssue,
    CatalogRoleIssue,
    GuildCatalogDiagnosticResult,
    WorkflowCatalogDiagnostic,
    WorkflowCatalogSectionDiagnostic,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)


class WorkflowCatalogDiagnosticService:
    """Compare persisted workflow catalogs with live Discord resources."""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowDefinitionRepository,
        catalog_entry_repository: CatalogEntryRepository,
        owner_repository: GuildAIQuestionnaireOwnerRepository,
        discovery_service: RoleChannelDiscoveryService,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.catalog_entry_repository = catalog_entry_repository
        self.owner_repository = owner_repository
        self.discovery_service = discovery_service

    async def inspect(
        self,
        guild: discord.Guild,
    ) -> GuildCatalogDiagnosticResult:
        """Return a read-only workflow/catalog diagnostic snapshot."""

        workflows = await self.workflow_repository.list_for_guild(
            guild.id,
        )
        owner_workflow_key = await self.owner_repository.get(
            guild.id,
        )
        snapshot = self.discovery_service.build_snapshot(
            guild,
        )

        live_roles_by_id = {
            role.role_id: role
            for role in snapshot.roles
        }
        live_channels_by_id = {
            channel.channel_id: channel.channel_name
            for channel in snapshot.channels
        }
        discord_channels_by_id = {
            channel.id: channel
            for channel in guild.channels
        }

        results: list[WorkflowCatalogDiagnostic] = []

        for workflow in workflows:
            structure_issues: list[str] = []

            category_name = self._resource_name(
                discord_channels_by_id,
                workflow.category_id,
            )
            if workflow.category_id is None:
                structure_issues.append(
                    "catégorie non configurée"
                )
            elif category_name is None:
                structure_issues.append(
                    "catégorie configurée absente de Discord"
                )

            management_channel_name = self._resource_name(
                discord_channels_by_id,
                workflow.management_channel_id,
            )
            if workflow.management_channel_id is None:
                structure_issues.append(
                    "salon de gestion non configuré"
                )
            elif management_channel_name is None:
                structure_issues.append(
                    "salon de gestion absent de Discord"
                )

            execution_channel_names = tuple(
                sorted(
                    (
                        discord_channels_by_id[channel_id].name
                        for channel_id in workflow.channel_ids
                        if channel_id in discord_channels_by_id
                    ),
                    key=str.casefold,
                )
            )
            missing_execution_count = sum(
                1
                for channel_id in workflow.channel_ids
                if channel_id not in discord_channels_by_id
            )
            if not workflow.channel_ids:
                structure_issues.append(
                    "aucun salon d'exécution configuré"
                )
            elif missing_execution_count:
                structure_issues.append(
                    f"{missing_execution_count} salon(s) d'exécution absent(s)"
                )

            primary_role_snapshot = (
                live_roles_by_id.get(
                    workflow.primary_role_id,
                )
                if workflow.primary_role_id is not None
                else None
            )
            primary_role_name = (
                primary_role_snapshot.role_name
                if primary_role_snapshot is not None
                else None
            )

            if workflow.primary_role_id is None:
                structure_issues.append(
                    "rôle principal non configuré"
                )
            elif primary_role_snapshot is None:
                structure_issues.append(
                    "rôle principal absent de Discord"
                )

            primary_role_explicit_channel_names = (
                tuple(
                    sorted(
                        (
                            live_channels_by_id[channel_id]
                            for channel_id
                            in primary_role_snapshot.explicit_channel_ids
                            if channel_id in live_channels_by_id
                        ),
                        key=str.casefold,
                    )
                )
                if primary_role_snapshot is not None
                else ()
            )

            catalog_results: list[WorkflowCatalogSectionDiagnostic] = []

            for binding in workflow.catalogs:
                catalog = binding.catalog

                if not binding.enabled or not catalog.enabled:
                    continue

                entries = await self.catalog_entry_repository.list_for_catalog(
                    guild_id=guild.id,
                    catalog_key=catalog.catalog_key,
                )

                target_role_ids = {
                    target.role_id
                    for entry in entries
                    for target in entry.targets
                }
                detected_roles = tuple(
                    role
                    for role in snapshot.roles
                    if role.role_name.startswith(
                        catalog.role_prefix,
                    )
                    and role.role_name != catalog.role_prefix
                )

                linked_channel_names = tuple(
                    sorted(
                        {
                            live_channels_by_id[channel_id]
                            for role in detected_roles
                            for channel_id in role.explicit_channel_ids
                            if channel_id in live_channels_by_id
                        },
                        key=str.casefold,
                    )
                )

                incomplete_entries: list[CatalogMetadataIssue] = []

                for entry in entries:
                    missing_fields: list[str] = []

                    if not entry.label or not entry.label.strip():
                        missing_fields.append(
                            "label"
                        )

                    if not entry.description or not entry.description.strip():
                        missing_fields.append(
                            "description"
                        )

                    if not missing_fields:
                        continue

                    incomplete_entries.append(
                        CatalogMetadataIssue(
                            entry_key=entry.entry_key,
                            label=entry.label,
                            missing_fields=tuple(
                                missing_fields,
                            ),
                        )
                    )

                issues: dict[str, set[str]] = {}
                issue_channels: dict[str, set[str]] = {}

                for role in detected_roles:
                    reasons = issues.setdefault(
                        role.role_name,
                        set(),
                    )
                    channels = issue_channels.setdefault(
                        role.role_name,
                        set(),
                    )
                    channels.update(
                        live_channels_by_id[channel_id]
                        for channel_id in role.explicit_channel_ids
                        if channel_id in live_channels_by_id
                    )

                    if not role.role_manageable:
                        reasons.add(
                            "rôle non manipulable"
                        )

                    if len(role.explicit_channel_ids) == 0:
                        reasons.add(
                            "aucun salon/forum explicite"
                        )
                    elif len(role.explicit_channel_ids) > 1:
                        reasons.add(
                            "plusieurs salons/forums explicites"
                        )

                    if role.role_id not in target_role_ids:
                        reasons.add(
                            "absent de la BDD"
                        )

                for entry in entries:
                    for target in entry.targets:
                        live_role = live_roles_by_id.get(
                            target.role_id,
                        )

                        if live_role is None:
                            issues.setdefault(
                                target.role_name,
                                set(),
                            ).add(
                                "rôle BDD absent de Discord"
                            )
                            continue

                        if not live_role.role_name.startswith(
                            catalog.role_prefix,
                        ):
                            issues.setdefault(
                                live_role.role_name,
                                set(),
                            ).add(
                                "ne correspond plus au pattern"
                            )

                        if target.channel_id not in live_channels_by_id:
                            issues.setdefault(
                                live_role.role_name,
                                set(),
                            ).add(
                                "salon/forum BDD absent de Discord"
                            )
                        elif target.channel_id not in live_role.explicit_channel_ids:
                            issues.setdefault(
                                live_role.role_name,
                                set(),
                            ).add(
                                "mapping BDD différent des permissions explicites"
                            )

                role_issues = tuple(
                    CatalogRoleIssue(
                        role_name=role_name,
                        channel_names=tuple(
                            sorted(
                                issue_channels.get(
                                    role_name,
                                    set(),
                                ),
                                key=str.casefold,
                            )
                        ),
                        reasons=tuple(
                            sorted(
                                reasons,
                                key=str.casefold,
                            )
                        ),
                    )
                    for role_name, reasons in sorted(
                        issues.items(),
                        key=lambda item: item[0].casefold(),
                    )
                    if reasons
                )

                unsynced_role_names = tuple(
                    sorted(
                        (
                            role.role_name
                            for role in detected_roles
                            if role.role_id not in target_role_ids
                        ),
                        key=str.casefold,
                    )
                )

                complete_entry_count = sum(
                    1
                    for entry in entries
                    if entry.enabled
                    and bool(entry.label and entry.label.strip())
                    and bool(entry.description and entry.description.strip())
                )

                catalog_results.append(
                    WorkflowCatalogSectionDiagnostic(
                        catalog_key=catalog.catalog_key,
                        display_name=catalog.display_name,
                        role_prefix=catalog.role_prefix,
                        detected_role_names=tuple(
                            sorted(
                                (
                                    role.role_name
                                    for role in detected_roles
                                ),
                                key=str.casefold,
                            )
                        ),
                        linked_channel_names=linked_channel_names,
                        entry_count=len(entries),
                        complete_entry_count=complete_entry_count,
                        incomplete_entries=tuple(
                            incomplete_entries,
                        ),
                        unsynced_role_names=unsynced_role_names,
                        role_issues=role_issues,
                    )
                )

            results.append(
                WorkflowCatalogDiagnostic(
                    workflow_key=workflow.workflow_key,
                    title=workflow.title,
                    command_name=workflow.command_name,
                    category_name=category_name,
                    management_channel_name=management_channel_name,
                    execution_channel_names=execution_channel_names,
                    primary_role_name=primary_role_name,
                    primary_role_explicit_channel_names=(
                        primary_role_explicit_channel_names
                    ),
                    ai_questionnaire_owner=(
                        owner_workflow_key == workflow.workflow_key
                    ),
                    structure_issues=tuple(
                        structure_issues,
                    ),
                    catalogs=tuple(
                        catalog_results,
                    ),
                )
            )

        return GuildCatalogDiagnosticResult(
            workflows=tuple(
                results,
            ),
        )

    @staticmethod
    def _resource_name(
        resources: dict[int, discord.abc.GuildChannel],
        resource_id: int | None,
    ) -> str | None:
        if resource_id is None:
            return None

        resource = resources.get(
            resource_id,
        )

        if resource is None:
            return None

        return resource.name
