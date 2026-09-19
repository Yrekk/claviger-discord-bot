import discord

from claviger.models.catalogs.catalog_administration_model import (
    CatalogMetadataCandidate,
    CatalogSynchronizationSummary,
)
from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.catalog_entry_model import CatalogEntry
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.catalog_entry_synchronization_service import (
    CatalogEntrySynchronizationService,
)


class CatalogAdministrationService:
    """Coordinate explicit catalog sync and human metadata administration."""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowDefinitionRepository,
        entry_repository: CatalogEntryRepository,
        synchronization_service: CatalogEntrySynchronizationService,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.entry_repository = entry_repository
        self.synchronization_service = synchronization_service

    async def synchronize_all(
        self,
        guild: discord.Guild,
    ) -> tuple[CatalogSynchronizationSummary, ...]:
        """Synchronize every active catalog bound to an active workflow."""

        catalogs = await self._list_active_catalogs(
            guild.id,
        )
        summaries: list[CatalogSynchronizationSummary] = []

        for catalog in catalogs:
            try:
                entries = await self.synchronization_service.synchronize(
                    guild=guild,
                    catalog=catalog,
                )
            except Exception as error:
                summaries.append(
                    CatalogSynchronizationSummary(
                        catalog_key=catalog.catalog_key,
                        display_name=catalog.display_name,
                        role_prefix=catalog.role_prefix,
                        entry_count=None,
                        incomplete_metadata_count=None,
                        error=f"{type(error).__name__}: {error}",
                    )
                )
                continue

            summaries.append(
                CatalogSynchronizationSummary(
                    catalog_key=catalog.catalog_key,
                    display_name=catalog.display_name,
                    role_prefix=catalog.role_prefix,
                    entry_count=len(entries),
                    incomplete_metadata_count=sum(
                        1
                        for entry in entries
                        if self._metadata_incomplete(
                            entry,
                        )
                    ),
                )
            )

        return tuple(
            summaries,
        )

    async def next_incomplete(
        self,
        guild_id: int,
    ) -> CatalogMetadataCandidate | None:
        """Return the first enabled active entry missing required metadata."""

        catalogs = await self._list_active_catalogs(
            guild_id,
        )

        for catalog in catalogs:
            entries = await self.entry_repository.list_for_catalog(
                guild_id=guild_id,
                catalog_key=catalog.catalog_key,
            )

            for entry in entries:
                if not entry.enabled or not self._metadata_incomplete(
                    entry,
                ):
                    continue

                return self._build_metadata_candidate(
                    catalog,
                    entry,
                )

        return None

    async def count_entries(
        self,
        guild_id: int,
    ) -> int:
        """Count enabled entries across active workflow catalogs."""

        catalogs = await self._list_active_catalogs(
            guild_id,
        )
        count = 0

        for catalog in catalogs:
            entries = await self.entry_repository.list_for_catalog(
                guild_id=guild_id,
                catalog_key=catalog.catalog_key,
            )
            count += sum(
                1
                for entry in entries
                if entry.enabled
            )

        return count

    async def count_incomplete(
        self,
        guild_id: int,
    ) -> int:
        """Count enabled active entries missing label or description."""

        catalogs = await self._list_active_catalogs(
            guild_id,
        )
        count = 0

        for catalog in catalogs:
            entries = await self.entry_repository.list_for_catalog(
                guild_id=guild_id,
                catalog_key=catalog.catalog_key,
            )
            count += sum(
                1
                for entry in entries
                if entry.enabled
                and self._metadata_incomplete(
                    entry,
                )
            )

        return count

    async def update_metadata(
        self,
        *,
        guild_id: int,
        catalog_key: str,
        entry_key: str,
        label: str,
        description: str,
        emoji: str | None,
    ) -> CatalogMetadataCandidate | None:
        """Persist human metadata without mutating any Discord target."""

        active_catalogs = await self._list_active_catalogs(
            guild_id,
        )
        catalog = next(
            (
                candidate
                for candidate in active_catalogs
                if candidate.catalog_key == catalog_key
            ),
            None,
        )

        if catalog is None:
            raise ValueError(
                "Catalog is no longer active or bound to an active workflow."
            )

        await self.entry_repository.update_metadata(
            guild_id=guild_id,
            catalog_key=catalog.catalog_key,
            entry_key=entry_key,
            label=label,
            description=description,
            emoji=emoji,
        )

        return await self.next_incomplete(
            guild_id,
        )

    async def _list_active_catalogs(
        self,
        guild_id: int,
    ) -> tuple[CatalogDefinition, ...]:
        """Return each active bound catalog once in stable workflow order."""

        workflows = await self.workflow_repository.list_for_guild(
            guild_id,
        )
        catalogs: list[CatalogDefinition] = []
        seen: set[str] = set()

        for workflow in workflows:
            if not workflow.enabled:
                continue

            for binding in workflow.catalogs:
                catalog = binding.catalog

                if (
                    not binding.enabled
                    or not catalog.enabled
                    or catalog.catalog_key in seen
                ):
                    continue

                seen.add(
                    catalog.catalog_key,
                )
                catalogs.append(
                    catalog,
                )

        return tuple(
            catalogs,
        )

    @staticmethod
    def _metadata_incomplete(
        entry: CatalogEntry,
    ) -> bool:
        """Return whether required questionnaire metadata is missing."""

        return not bool(
            entry.label
            and entry.label.strip()
            and entry.description
            and entry.description.strip()
        )

    @staticmethod
    def _build_metadata_candidate(
        catalog: CatalogDefinition,
        entry: CatalogEntry,
    ) -> CatalogMetadataCandidate:
        """Convert one persisted entry into an ADMIN metadata candidate."""

        return CatalogMetadataCandidate(
            catalog_key=catalog.catalog_key,
            catalog_display_name=catalog.display_name,
            entry_key=entry.entry_key,
            label=entry.label,
            description=entry.description,
            emoji=entry.emoji,
            target_role_names=tuple(
                sorted(
                    {
                        target.role_name
                        for target in entry.targets
                    },
                    key=str.casefold,
                )
            ),
            target_channel_names=tuple(
                sorted(
                    {
                        target.channel_name
                        for target in entry.targets
                    },
                    key=str.casefold,
                )
            ),
        )
