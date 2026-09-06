from pathlib import Path

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
)
from claviger.database.schema import DatabaseSchema
from claviger.models.catalog_sync_model import (
    CatalogStateUpdate,
    CatalogSyncEntry,
    CatalogSyncPlan,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
    MemberInterestNotFoundError,
)


async def create_repository(
    tmp_path: Path,
) -> InterestCatalogRepository:
    """Create an initialized temporary interest catalog repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return InterestCatalogRepository(
        database,
    )


async def create_interest(
    repository: InterestCatalogRepository,
    *,
    guild_id: int = 123,
    role_id: int = 456,
    role_name: str = "interest-ludus",
    interest_key: str = "ludus",
    channel_id: int = 789,
    channel_name: str = "ludus",
) -> None:
    """Create one discovered member interest."""

    await repository.create_discovered(
        guild_id=guild_id,
        role_id=role_id,
        role_name=role_name,
        interest_key=interest_key,
        channel_id=channel_id,
        channel_name=channel_name,
    )


@pytest.mark.asyncio
async def test_list_for_guild_returns_empty_catalog(
    tmp_path: Path,
) -> None:
    """Return an empty list when a guild has no known interests."""

    repository = await create_repository(
        tmp_path,
    )

    assert await repository.list_for_guild(123) == []


@pytest.mark.asyncio
async def test_create_discovered_interest_uses_safe_defaults(
    tmp_path: Path,
) -> None:
    """Create discovered interests without inventing human metadata."""

    repository = await create_repository(
        tmp_path,
    )

    interest = await repository.create_discovered(
        guild_id=123,
        role_id=456,
        role_name="interest-ludus",
        interest_key="ludus",
        channel_id=789,
        channel_name="ludus",
    )

    assert interest.guild_id == 123
    assert interest.role_id == 456
    assert interest.role_name == "interest-ludus"
    assert interest.interest_key == "ludus"
    assert interest.channel_id == 789
    assert interest.channel_name == "ludus"

    assert interest.label is None
    assert interest.description is None
    assert interest.emoji is None

    assert interest.sort_order == 0
    assert interest.enabled is True

    assert interest.discord_present is True
    assert interest.role_manageable is True
    assert interest.channel_present is True
    assert interest.mapping_valid is True
    assert interest.matches_policy is True


@pytest.mark.asyncio
async def test_get_returns_interest_by_stable_role_identity(
    tmp_path: Path,
) -> None:
    """Load an interest using guild and Discord role IDs."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None
    assert interest.role_name == "interest-ludus"
    assert interest.channel_id == 789


@pytest.mark.asyncio
async def test_get_returns_none_for_unknown_role(
    tmp_path: Path,
) -> None:
    """Return None when the role has never been catalogued."""

    repository = await create_repository(
        tmp_path,
    )

    assert (
        await repository.get(
            123,
            999,
        )
        is None
    )


@pytest.mark.asyncio
async def test_catalogs_are_isolated_by_guild(
    tmp_path: Path,
) -> None:
    """Keep identical role IDs isolated between Discord guilds."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
        guild_id=123,
        role_name="interest-ludus-a",
    )

    await create_interest(
        repository,
        guild_id=456,
        role_name="interest-ludus-b",
    )

    first = await repository.get(
        123,
        456,
    )

    second = await repository.get(
        456,
        456,
    )

    assert first is not None
    assert second is not None

    assert first.role_name == "interest-ludus-a"
    assert second.role_name == "interest-ludus-b"


@pytest.mark.asyncio
async def test_refresh_discovered_updates_discord_owned_data(
    tmp_path: Path,
) -> None:
    """Refresh technical Discord data for a known interest."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.refresh_discovered(
        guild_id=123,
        role_id=456,
        role_name="interest-games",
        interest_key="games",
        channel_id=999,
        channel_name="gaming",
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None

    assert interest.role_name == "interest-games"
    assert interest.interest_key == "games"
    assert interest.channel_id == 999
    assert interest.channel_name == "gaming"

    assert interest.discord_present is True
    assert interest.channel_present is True
    assert interest.matches_policy is True


@pytest.mark.asyncio
async def test_refresh_discovered_preserves_human_metadata(
    tmp_path: Path,
) -> None:
    """Never overwrite human-managed metadata during Discord refresh."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_metadata(
        123,
        456,
        label="Jeux vidéo",
        description="Discussions autour des jeux vidéo.",
        emoji="🎮",
    )

    await repository.refresh_discovered(
        guild_id=123,
        role_id=456,
        role_name="interest-games",
        interest_key="games",
        channel_id=999,
        channel_name="gaming",
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None

    assert interest.label == "Jeux vidéo"
    assert interest.description == "Discussions autour des jeux vidéo."
    assert interest.emoji == "🎮"


@pytest.mark.asyncio
async def test_update_sync_state_preserves_known_discord_identity(
    tmp_path: Path,
) -> None:
    """Record missing Discord objects without erasing their known IDs."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_sync_state(
        123,
        456,
        discord_present=True,
        role_manageable=True,
        channel_present=False,
        mapping_valid=True,
        matches_policy=True,
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None

    assert interest.role_id == 456
    assert interest.role_name == "interest-ludus"
    assert interest.channel_id == 789
    assert interest.channel_name == "ludus"

    assert interest.discord_present is True
    assert interest.channel_present is False
    assert interest.matches_policy is True
    assert interest.role_manageable is True


@pytest.mark.asyncio
async def test_update_metadata_supports_intentionally_empty_description(
    tmp_path: Path,
) -> None:
    """Persist an empty description as configured rather than missing."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_metadata(
        123,
        456,
        label="Jeux vidéo",
        description="",
        emoji=None,
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None
    assert interest.label == "Jeux vidéo"
    assert interest.description == ""
    assert interest.emoji is None
    assert interest.is_configured is True


@pytest.mark.asyncio
async def test_get_next_incomplete_returns_available_unconfigured_interest(
    tmp_path: Path,
) -> None:
    """Return the next valid interest requiring human metadata."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
        role_id=100,
        role_name="interest-ia",
        interest_key="ia",
        channel_id=200,
        channel_name="ia",
    )

    await create_interest(
        repository,
        role_id=101,
        role_name="interest-ludus",
        interest_key="ludus",
        channel_id=201,
        channel_name="ludus",
    )

    await repository.update_metadata(
        123,
        100,
        label="Intelligence artificielle",
        description="Discussions autour de l'IA.",
        emoji="🤖",
    )

    interest = await repository.get_next_incomplete(
        123,
    )

    assert interest is not None
    assert interest.role_id == 101


@pytest.mark.asyncio
async def test_get_next_incomplete_ignores_invalid_discord_state(
    tmp_path: Path,
) -> None:
    """Do not configure interests whose Discord mapping is currently invalid."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_sync_state(
        123,
        456,
        discord_present=True,
        role_manageable=True,
        channel_present=False,
        mapping_valid=True,
        matches_policy=True,
    )

    assert (
        await repository.get_next_incomplete(
            123,
        )
        is None
    )


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_interest(
    tmp_path: Path,
) -> None:
    """Reject refresh attempts for roles not present in the catalog."""

    repository = await create_repository(
        tmp_path,
    )

    with pytest.raises(
        MemberInterestNotFoundError,
    ):
        await repository.refresh_discovered(
            guild_id=123,
            role_id=456,
            role_name="interest-ludus",
            interest_key="ludus",
            channel_id=789,
            channel_name="ludus",
        )


@pytest.mark.asyncio
async def test_repository_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite implicitly while reading the interest catalog."""

    database_path = tmp_path / "claviger.db"

    database = DatabaseConnection(
        database_path,
    )

    repository = InterestCatalogRepository(
        database,
    )

    with pytest.raises(
        DatabaseMissingError,
    ):
        await repository.list_for_guild(
            123,
        )

    assert database_path.exists() is False


@pytest.mark.asyncio
async def test_get_next_incomplete_ignores_unmanageable_role(
    tmp_path: Path,
) -> None:
    """Do not configure interests whose Discord role cannot be managed."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_sync_state(
        123,
        456,
        discord_present=True,
        role_manageable=False,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )

    assert (
        await repository.get_next_incomplete(
            123,
        )
        is None
    )


@pytest.mark.asyncio
async def test_get_next_incomplete_ignores_invalid_mapping(
    tmp_path: Path,
) -> None:
    """Do not configure interests whose role-to-channel mapping is invalid."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_sync_state(
        123,
        456,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=False,
        matches_policy=True,
    )

    assert (
        await repository.get_next_incomplete(
            123,
        )
        is None
    )


@pytest.mark.asyncio
async def test_create_discovered_preserves_unmanageable_role_state(
    tmp_path: Path,
) -> None:
    """Persist Discord manageability when first cataloguing a role."""

    repository = await create_repository(
        tmp_path,
    )

    interest = await repository.create_discovered(
        guild_id=123,
        role_id=456,
        role_name="interest-ludus",
        interest_key="ludus",
        channel_id=789,
        channel_name="ludus",
        role_manageable=False,
    )

    assert interest.role_manageable is False


@pytest.mark.asyncio
async def test_refresh_discovered_preserves_unmanageable_role_state(
    tmp_path: Path,
) -> None:
    """Keep Discord manageability state during technical refresh."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.refresh_discovered(
        guild_id=123,
        role_id=456,
        role_name="interest-ludus",
        interest_key="ludus",
        channel_id=789,
        channel_name="ludus",
        role_manageable=False,
    )

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None
    assert interest.role_manageable is False


@pytest.mark.asyncio
async def test_apply_sync_plan_does_not_commit_transaction(
    tmp_path: Path,
) -> None:
    """Leave transaction ownership to the catalog coordinator."""

    repository = await create_repository(
        tmp_path,
    )

    plan = CatalogSyncPlan(
        creates=(
            CatalogSyncEntry(
                role_id=999,
                role_name="interest-machinae",
                catalog_key="machinae",
                channel_id=888,
                channel_name="machinae",
                role_manageable=True,
            ),
        ),
        refreshes=(),
        state_updates=(),
        warnings=(),
    )

    async with repository.database.connect() as connection:
        await connection.execute("BEGIN IMMEDIATE")

        await repository.apply_sync_plan(
            connection,
            123,
            plan,
        )

        await connection.rollback()

    assert (
        await repository.get(
            123,
            999,
        )
        is None
    )


@pytest.mark.asyncio
async def test_apply_sync_plan_preserves_historical_identity(
    tmp_path: Path,
) -> None:
    """Update sync state without losing stable historical catalog data."""

    repository = await create_repository(
        tmp_path,
    )

    await create_interest(
        repository,
    )

    await repository.update_metadata(
        123,
        456,
        label="Jeux vidéo",
        description="Discussions autour des jeux vidéo.",
        emoji="🎮",
    )

    plan = CatalogSyncPlan(
        creates=(),
        refreshes=(),
        state_updates=(
            CatalogStateUpdate(
                role_id=456,
                role_name="legacy-ludus",
                catalog_key=None,
                channel_name="ludus-renamed",
                discord_present=True,
                role_manageable=True,
                channel_present=True,
                mapping_valid=False,
                matches_policy=False,
            ),
        ),
        warnings=(),
    )

    async with repository.database.connect() as connection:
        await connection.execute("BEGIN IMMEDIATE")

        await repository.apply_sync_plan(
            connection,
            123,
            plan,
        )

        await connection.commit()

    interest = await repository.get(
        123,
        456,
    )

    assert interest is not None

    assert interest.role_id == 456
    assert interest.role_name == "legacy-ludus"

    assert interest.interest_key == "ludus"

    assert interest.channel_id == 789
    assert interest.channel_name == "ludus-renamed"

    assert interest.label == "Jeux vidéo"
    assert interest.description == "Discussions autour des jeux vidéo."
    assert interest.emoji == "🎮"

    assert interest.discord_present is True
    assert interest.role_manageable is True
    assert interest.channel_present is True
    assert interest.mapping_valid is False
    assert interest.matches_policy is False
