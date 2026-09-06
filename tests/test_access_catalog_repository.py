from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
    AdultAccessNotFoundError,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)


async def create_repository(
    tmp_path: Path,
) -> AccessCatalogRepository:
    """Create an initialized temporary adult access repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return AccessCatalogRepository(
        database,
    )


@pytest.mark.asyncio
async def test_create_discovered_access_uses_shared_catalog_repository(
    tmp_path: Path,
) -> None:
    """Create an adult access through the shared repository implementation."""

    repository = await create_repository(
        tmp_path,
    )

    access = await repository.create_discovered(
        guild_id=123,
        role_id=456,
        role_name="access-ia-futa",
        access_key="ia-futa",
        channel_id=789,
        channel_name="ia-futa",
    )

    assert access.guild_id == 123
    assert access.role_id == 456
    assert access.role_name == "access-ia-futa"
    assert access.access_key == "ia-futa"

    assert access.channel_id == 789
    assert access.channel_name == "ia-futa"

    assert access.label is None
    assert access.description is None
    assert access.emoji is None

    assert access.enabled is True
    assert access.discord_present is True
    assert access.role_manageable is True
    assert access.channel_present is True
    assert access.mapping_valid is True
    assert access.matches_policy is True


@pytest.mark.asyncio
async def test_access_and_interest_catalogs_use_separate_tables(
    tmp_path: Path,
) -> None:
    """Keep adult access and member interest catalogs isolated."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    access_repository = AccessCatalogRepository(
        database,
    )
    interest_repository = InterestCatalogRepository(
        database,
    )

    await access_repository.create_discovered(
        guild_id=123,
        role_id=456,
        role_name="access-ia-futa",
        access_key="ia-futa",
        channel_id=789,
        channel_name="ia-futa",
    )

    accesses = await access_repository.list_for_guild(
        123,
    )
    interests = await interest_repository.list_for_guild(
        123,
    )

    assert len(accesses) == 1
    assert interests == []


@pytest.mark.asyncio
async def test_access_repository_reuses_metadata_workflow(
    tmp_path: Path,
) -> None:
    """Use the shared metadata and incomplete-entry workflow."""

    repository = await create_repository(
        tmp_path,
    )

    await repository.create_discovered(
        guild_id=123,
        role_id=456,
        role_name="access-ia-futa",
        access_key="ia-futa",
        channel_id=789,
        channel_name="ia-futa",
    )

    incomplete = await repository.get_next_incomplete(
        123,
    )

    assert incomplete is not None
    assert incomplete.role_id == 456

    await repository.update_metadata(
        123,
        456,
        label="IA Futa",
        description="Accès aux générations IA Futa.",
        emoji="🔞",
    )

    assert (
        await repository.get_next_incomplete(
            123,
        )
        is None
    )

    access = await repository.get(
        123,
        456,
    )

    assert access is not None
    assert access.label == "IA Futa"
    assert access.description == "Accès aux générations IA Futa."
    assert access.emoji == "🔞"


@pytest.mark.asyncio
async def test_refresh_rejects_unknown_adult_access(
    tmp_path: Path,
) -> None:
    """Use the adult access specific not-found error."""

    repository = await create_repository(
        tmp_path,
    )

    with pytest.raises(
        AdultAccessNotFoundError,
    ):
        await repository.refresh_discovered(
            guild_id=123,
            role_id=456,
            role_name="access-ia-futa",
            access_key="ia-futa",
            channel_id=789,
            channel_name="ia-futa",
        )
