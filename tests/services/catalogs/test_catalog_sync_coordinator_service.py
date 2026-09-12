from pathlib import Path
from unittest.mock import MagicMock

import discord
import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)
from claviger.services.catalog_registry_service import CatalogRegistry
from claviger.services.catalog_sync_coordinator_service import (
    CatalogSyncCoordinatorService,
)
from claviger.services.catalog_sync_planner_service import (
    CatalogSyncPlanner,
)
from claviger.services.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)


class FailingAccessCatalogRepository(
    AccessCatalogRepository,
):
    """Simulate an adult access failure during atomic synchronization."""

    async def apply_sync_plan(
        self,
        connection,
        guild_id,
        plan,
    ) -> None:
        raise RuntimeError("Simulated access catalog failure.")


def create_policy() -> GuildPolicy:
    """Create a guild policy using both catalog families."""

    return GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Civis Noctis - 18+",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        salutations_channel_name="salutations",
        adult_access_channel_name="aditus-noctis",
        role_management_enabled=True,
        adult_access_enabled=True,
    )


def create_guild() -> MagicMock:
    """Create the Discord guild required by the coordinator."""

    guild = MagicMock(
        spec=discord.Guild,
    )

    guild.id = 123

    return guild


def create_snapshot() -> GuildRoleChannelSnapshot:
    """Create one valid Interest and one valid Access snapshot."""

    return GuildRoleChannelSnapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(200,),
            ),
            DiscordRoleSnapshot(
                role_id=101,
                role_name="access-ia-futa",
                role_manageable=True,
                explicit_channel_ids=(201,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=200,
                channel_name="ia",
            ),
            DiscordChannelSnapshot(
                channel_id=201,
                channel_name="ia-futa",
            ),
        ),
    )


async def create_database(
    tmp_path: Path,
) -> DatabaseConnection:
    """Create an initialized temporary Claviger database."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return database


@pytest.mark.asyncio
async def test_sync_applies_interest_and_access_catalogs_together(
    tmp_path: Path,
) -> None:
    """Synchronize every registered catalog from one Discord snapshot."""

    database = await create_database(
        tmp_path,
    )

    interest_repository = InterestCatalogRepository(
        database,
    )
    access_repository = AccessCatalogRepository(
        database,
    )

    registry = CatalogRegistry(
        interest_repository=interest_repository,
        access_repository=access_repository,
    )

    discovery_service = MagicMock(
        spec=RoleChannelDiscoveryService,
    )
    discovery_service.build_snapshot.return_value = create_snapshot()

    coordinator = CatalogSyncCoordinatorService(
        database=database,
        registry=registry,
        discovery_service=discovery_service,
        planner=CatalogSyncPlanner(),
    )

    result = await coordinator.sync(
        create_guild(),
        create_policy(),
    )

    discovery_service.build_snapshot.assert_called_once()

    assert result.change_count == 2
    assert result.warning_count == 0

    interest = await interest_repository.get(
        123,
        100,
    )
    access = await access_repository.get(
        123,
        101,
    )

    assert interest is not None
    assert interest.interest_key == "ia"

    assert access is not None
    assert access.access_key == "ia-futa"


@pytest.mark.asyncio
async def test_sync_rolls_back_all_catalogs_when_second_catalog_fails(
    tmp_path: Path,
) -> None:
    """Rollback Interest when Access fails in the same transaction."""

    database = await create_database(
        tmp_path,
    )

    interest_repository = InterestCatalogRepository(
        database,
    )
    access_repository = FailingAccessCatalogRepository(
        database,
    )

    registry = CatalogRegistry(
        interest_repository=interest_repository,
        access_repository=access_repository,
    )

    discovery_service = MagicMock(
        spec=RoleChannelDiscoveryService,
    )
    discovery_service.build_snapshot.return_value = create_snapshot()

    coordinator = CatalogSyncCoordinatorService(
        database=database,
        registry=registry,
        discovery_service=discovery_service,
        planner=CatalogSyncPlanner(),
    )

    with pytest.raises(
        RuntimeError,
        match="Simulated access catalog failure",
    ):
        await coordinator.sync(
            create_guild(),
            create_policy(),
        )

    assert (
        await interest_repository.get(
            123,
            100,
        )
        is None
    )

    assert (
        await access_repository.get(
            123,
            101,
        )
        is None
    )


@pytest.mark.asyncio
async def test_sync_reports_invalid_mapping_without_writing_catalog_entry(
    tmp_path: Path,
) -> None:
    """Return planner warnings without persisting invalid new mappings."""

    database = await create_database(
        tmp_path,
    )

    interest_repository = InterestCatalogRepository(
        database,
    )
    access_repository = AccessCatalogRepository(
        database,
    )

    registry = CatalogRegistry(
        interest_repository=interest_repository,
        access_repository=access_repository,
    )

    snapshot = GuildRoleChannelSnapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=100,
                role_name="interest-ia",
                role_manageable=True,
                explicit_channel_ids=(),
            ),
        ),
        channels=(),
    )

    discovery_service = MagicMock(
        spec=RoleChannelDiscoveryService,
    )
    discovery_service.build_snapshot.return_value = snapshot

    coordinator = CatalogSyncCoordinatorService(
        database=database,
        registry=registry,
        discovery_service=discovery_service,
        planner=CatalogSyncPlanner(),
    )

    result = await coordinator.sync(
        create_guild(),
        create_policy(),
    )

    assert result.change_count == 0
    assert result.warning_count == 1

    interest_result = result.catalogs[0]

    assert interest_result.catalog_key == "member_interests"
    assert len(interest_result.plan.warnings) == 1
    assert interest_result.plan.warnings[0].code == "missing_channel_mapping"

    assert (
        await interest_repository.list_for_guild(
            123,
        )
        == []
    )
