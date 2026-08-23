from pathlib import Path

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseUnavailableError,
)


@pytest.mark.asyncio
async def test_database_connection_opens_sqlite_database(
    tmp_path: Path,
) -> None:
    """Open a temporary SQLite database successfully."""
    database_path = tmp_path / "claviger.db"

    database = DatabaseConnection(
        database_path,
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT 1"
        )

        result = await cursor.fetchone()

    assert result == (1,)
    assert database_path.exists()


@pytest.mark.asyncio
async def test_database_connection_enables_foreign_keys(
    tmp_path: Path,
) -> None:
    """Enable SQLite foreign key enforcement on every connection."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            "PRAGMA foreign_keys"
        )

        result = await cursor.fetchone()

    assert result == (1,)


@pytest.mark.asyncio
async def test_database_reports_available_database(
    tmp_path: Path,
) -> None:
    """Report an existing accessible SQLite database as available."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect():
        pass

    assert await database.is_available() is True


@pytest.mark.asyncio
async def test_database_raises_when_path_is_unavailable(
    tmp_path: Path,
) -> None:
    """Fail explicitly when SQLite cannot open the configured path."""
    database = DatabaseConnection(
        tmp_path / "missing-directory" / "claviger.db",
    )

    with pytest.raises(
        DatabaseUnavailableError,
        match="Unable to open SQLite database",
    ):
        async with database.connect():
            pass


@pytest.mark.asyncio
async def test_database_reports_unavailable_database(
    tmp_path: Path,
) -> None:
    """Report an inaccessible SQLite database as unavailable."""
    database = DatabaseConnection(
        tmp_path / "missing-directory" / "claviger.db",
    )

    assert await database.is_available() is False

def test_database_reports_missing_database(
    tmp_path: Path,
) -> None:
    """Report that the configured SQLite database does not exist."""
    database_path = tmp_path / "claviger.db"

    database = DatabaseConnection(
        database_path,
    )

    assert database.exists() is False
    assert database_path.exists() is False

@pytest.mark.asyncio
async def test_availability_check_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create a SQLite database while checking its availability."""
    database_path = tmp_path / "claviger.db"

    database = DatabaseConnection(
        database_path,
    )

    assert await database.is_available() is False
    assert database_path.exists() is False