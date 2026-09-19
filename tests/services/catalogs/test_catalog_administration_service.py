from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
)
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)
from claviger.services.catalogs.catalog_entry_synchronization_service import (
    CatalogEntrySynchronizationService,
)

pytestmark = pytest.mark.asyncio


def _catalog() -> CatalogDefinition:
    return CatalogDefinition(
        guild_id=123,
        catalog_key="interest",
        role_prefix="interest-",
        display_name="Membre",
        entry_name="Intérêt",
        description=None,
        sort_order=0,
        enabled=True,
    )


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        guild_id=123,
        workflow_key="member",
        command_name="membre",
        command_description="Configure les intérêts.",
        title="Membre",
        description=None,
        policy_key="member",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(100,),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=_catalog(),
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        primary_role_id=200,
    )


def _entry(
    *,
    label: str | None = None,
    description: str | None = None,
) -> CatalogEntry:
    return CatalogEntry(
        guild_id=123,
        catalog_key="interest",
        entry_key="test",
        label=label,
        description=description,
        emoji=None,
        sort_order=0,
        enabled=True,
        targets=(
            CatalogEntryTarget(
                guild_id=123,
                catalog_key="interest",
                entry_key="test",
                role_id=501,
                role_name="interest-test",
                channel_id=1501,
                channel_name="test-interest",
                variant="base",
                enabled=True,
                discord_present=True,
                role_manageable=True,
                channel_present=True,
                mapping_valid=True,
                matches_policy=True,
            ),
        ),
    )


async def test_next_incomplete_returns_human_metadata_candidate() -> None:
    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow(),
        )
    )
    entry_repository = Mock(spec=CatalogEntryRepository)
    entry_repository.list_for_catalog = AsyncMock(
        return_value=(
            _entry(),
        )
    )
    sync_service = Mock(spec=CatalogEntrySynchronizationService)

    service = CatalogAdministrationService(
        workflow_repository=workflow_repository,
        entry_repository=entry_repository,
        synchronization_service=sync_service,
    )

    candidate = await service.next_incomplete(
        123,
    )

    assert candidate is not None
    assert candidate.catalog_key == "interest"
    assert candidate.catalog_display_name == "Membre"
    assert candidate.entry_key == "test"
    assert candidate.target_role_names == (
        "interest-test",
    )
    assert candidate.target_channel_names == (
        "test-interest",
    )


async def test_update_metadata_only_updates_metadata_then_returns_next() -> None:
    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow(),
        )
    )
    entry_repository = Mock(spec=CatalogEntryRepository)
    entry_repository.update_metadata = AsyncMock(
        return_value=_entry(
            label="Test",
            description="Description",
        )
    )
    entry_repository.list_for_catalog = AsyncMock(
        return_value=(
            _entry(
                label="Test",
                description="Description",
            ),
        )
    )
    sync_service = Mock(spec=CatalogEntrySynchronizationService)

    service = CatalogAdministrationService(
        workflow_repository=workflow_repository,
        entry_repository=entry_repository,
        synchronization_service=sync_service,
    )

    next_candidate = await service.update_metadata(
        guild_id=123,
        catalog_key="interest",
        entry_key="test",
        label="Test",
        description="Description",
        emoji=None,
    )

    entry_repository.update_metadata.assert_awaited_once_with(
        guild_id=123,
        catalog_key="interest",
        entry_key="test",
        label="Test",
        description="Description",
        emoji=None,
    )
    sync_service.synchronize.assert_not_called()
    assert next_candidate is None


async def test_synchronize_all_uses_existing_generic_sync_backend() -> None:
    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow(),
        )
    )
    entry_repository = Mock(spec=CatalogEntryRepository)
    sync_service = Mock(spec=CatalogEntrySynchronizationService)
    sync_service.synchronize = AsyncMock(
        return_value=(
            _entry(),
        )
    )

    service = CatalogAdministrationService(
        workflow_repository=workflow_repository,
        entry_repository=entry_repository,
        synchronization_service=sync_service,
    )

    guild = Mock(spec=discord.Guild)
    guild.id = 123

    summaries = await service.synchronize_all(
        guild,
    )

    sync_service.synchronize.assert_awaited_once_with(
        guild=guild,
        catalog=_catalog(),
    )

    assert len(summaries) == 1
    assert summaries[0].catalog_key == "interest"
    assert summaries[0].entry_count == 1
    assert summaries[0].incomplete_metadata_count == 1
    assert summaries[0].succeeded is True



async def test_count_entries_ignores_disabled_entries() -> None:
    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow(),
        )
    )

    disabled = CatalogEntry(
        guild_id=123,
        catalog_key="interest",
        entry_key="disabled",
        label=None,
        description=None,
        emoji=None,
        sort_order=10,
        enabled=False,
        targets=(),
    )

    entry_repository = Mock(spec=CatalogEntryRepository)
    entry_repository.list_for_catalog = AsyncMock(
        return_value=(
            _entry(),
            disabled,
        )
    )
    sync_service = Mock(spec=CatalogEntrySynchronizationService)

    service = CatalogAdministrationService(
        workflow_repository=workflow_repository,
        entry_repository=entry_repository,
        synchronization_service=sync_service,
    )

    assert await service.count_entries(
        123,
    ) == 1
