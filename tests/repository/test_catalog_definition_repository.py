from pathlib import Path

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
)
from claviger.database.schema import DatabaseSchema
from claviger.models.catalog_definition_model import CatalogDefinition
from claviger.repositories.catalog_definition_repository import (
    CatalogDefinitionRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_repository(
    tmp_path: Path,
) -> tuple[
    DatabaseConnection,
    CatalogDefinitionRepository,
]:
    """Create an initialized catalog definition repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return (
        database,
        CatalogDefinitionRepository(
            database,
        ),
    )


async def _insert_catalog(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    catalog_key: str = "interests",
    role_prefix: str = "interest-",
    display_name: str = "Interests",
    entry_name: str = "Interest",
    description: str | None = None,
    sort_order: int = 0,
    enabled: bool = True,
) -> None:
    """Insert one catalog definition directly into the test database."""

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_catalogs (
                guild_id,
                catalog_key,
                role_prefix,
                display_name,
                entry_name,
                description,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                catalog_key,
                role_prefix,
                display_name,
                entry_name,
                description,
                sort_order,
                enabled,
            ),
        )

        await connection.commit()


async def test_get_returns_none_for_unknown_catalog(
    tmp_path: Path,
) -> None:
    """Return None when the requested catalog does not exist."""

    _, repository = await _create_repository(
        tmp_path,
    )

    result = await repository.get(
        guild_id=123,
        catalog_key="missing",
    )

    assert result is None


async def test_get_returns_catalog_definition(
    tmp_path: Path,
) -> None:
    """Load one complete catalog definition."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_catalog(
        database,
        catalog_key="premium-access",
        role_prefix="access-premium-",
        display_name="Premium access",
        entry_name="Premium channel",
        description="Premium areas.",
        sort_order=20,
        enabled=False,
    )

    result = await repository.get(
        guild_id=123,
        catalog_key="premium-access",
    )

    assert result == CatalogDefinition(
        guild_id=123,
        catalog_key="premium-access",
        role_prefix="access-premium-",
        display_name="Premium access",
        entry_name="Premium channel",
        description="Premium areas.",
        sort_order=20,
        enabled=False,
    )


async def test_list_for_guild_orders_catalogs(
    tmp_path: Path,
) -> None:
    """Return guild catalogs in their configured order."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_catalog(
        database,
        catalog_key="premium",
        role_prefix="access-premium-",
        display_name="Premium",
        entry_name="Premium access",
        sort_order=20,
    )

    await _insert_catalog(
        database,
        catalog_key="interests",
        role_prefix="interest-",
        display_name="Interests",
        entry_name="Interest",
        sort_order=10,
    )

    result = await repository.list_for_guild(
        123,
    )

    assert tuple(catalog.catalog_key for catalog in result) == (
        "interests",
        "premium",
    )


async def test_catalog_definitions_are_isolated_by_guild(
    tmp_path: Path,
) -> None:
    """Never expose another guild's catalog configuration."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_catalog(
        database,
        guild_id=123,
        catalog_key="first",
        role_prefix="first-",
        display_name="First",
        entry_name="First",
    )

    await _insert_catalog(
        database,
        guild_id=456,
        catalog_key="second",
        role_prefix="second-",
        display_name="Second",
        entry_name="Second",
    )

    first = await repository.list_for_guild(
        123,
    )

    second = await repository.list_for_guild(
        456,
    )

    assert tuple(catalog.catalog_key for catalog in first) == ("first",)

    assert tuple(catalog.catalog_key for catalog in second) == ("second",)


async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while reading missing catalog configuration."""

    database_path = tmp_path / "claviger.db"

    repository = CatalogDefinitionRepository(
        DatabaseConnection(
            database_path,
        )
    )

    with pytest.raises(
        DatabaseMissingError,
    ):
        await repository.get(
            guild_id=123,
            catalog_key="interests",
        )

    assert database_path.exists() is False
