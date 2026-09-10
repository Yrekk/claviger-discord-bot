from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    DatabaseSchema,
    UnsupportedSchemaVersionError,
)


@pytest.mark.asyncio
async def test_new_database_starts_with_schema_version_zero(
    tmp_path: Path,
) -> None:
    """Report version zero before the database schema is initialized."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    assert await schema.get_version() == 0


@pytest.mark.asyncio
async def test_initialize_sets_current_schema_version(
    tmp_path: Path,
) -> None:
    """Initialize a new database with the current schema version."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_initialize_rejects_already_initialized_database(
    tmp_path: Path,
) -> None:
    """Reject initialization when the database is already initialized."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    with pytest.raises(
        RuntimeError,
        match="Database is already initialized",
    ):
        await schema.initialize()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_initialize_rejects_newer_database_schema(
    tmp_path: Path,
) -> None:
    """Reject databases created by a newer incompatible Claviger version."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="newer than supported version",
    ):
        await schema.initialize()


@pytest.mark.asyncio
async def test_migrate_rejects_uninitialized_database(
    tmp_path: Path,
) -> None:
    """Reject migration when the database has not been initialized."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    with pytest.raises(
        RuntimeError,
        match="Database is not initialized",
    ):
        await schema.migrate()


@pytest.mark.asyncio
async def test_migrate_rejects_current_database_schema(
    tmp_path: Path,
) -> None:
    """Reject migration when the database is already current."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    with pytest.raises(
        RuntimeError,
        match="Database is already up to date",
    ):
        await schema.migrate()


@pytest.mark.asyncio
async def test_migrate_rejects_newer_database_schema(
    tmp_path: Path,
) -> None:
    """Reject migration of a database newer than this Claviger version."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    with pytest.raises(
        UnsupportedSchemaVersionError,
        match="newer than supported version",
    ):
        await schema.migrate()
