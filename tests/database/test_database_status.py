from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseUnavailableError,
)
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    DatabaseSchema,
)
from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)


@pytest.mark.asyncio
async def test_database_status_reports_missing_database(
    tmp_path: Path,
) -> None:
    """Report a database file that does not exist."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(database)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.MISSING
    assert status.current_version is None
    assert status.target_version == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_database_status_reports_uninitialized_database(
    tmp_path: Path,
) -> None:
    """Report an existing SQLite database with schema version zero."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect():
        pass

    schema = DatabaseSchema(database)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.UNINITIALIZED
    assert status.current_version == 0


@pytest.mark.asyncio
async def test_database_status_reports_ready_database(
    tmp_path: Path,
) -> None:
    """Report a database using the current schema version."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(database)

    await schema.initialize()

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.READY
    assert status.current_version == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_database_status_reports_integrity_failure(
    tmp_path: Path,
) -> None:
    """Fail closed when SQLite cannot validate the database structure."""

    database_path = tmp_path / "claviger.db"
    database_path.write_bytes(
        b"this is not a valid sqlite database"
    )

    database = DatabaseConnection(
        database_path,
    )
    schema = DatabaseSchema(database)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.INTEGRITY_FAILED
    assert status.current_version is None
    assert status.target_version == CURRENT_SCHEMA_VERSION


@pytest.mark.asyncio
async def test_database_status_stops_before_schema_read_when_quick_check_fails() -> None:
    """Never trust schema metadata after an explicit quick-check failure."""

    database = Mock(spec=DatabaseConnection)
    database.exists.return_value = True
    database.check_integrity = AsyncMock(return_value=False)

    schema = Mock(spec=DatabaseSchema)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.INTEGRITY_FAILED
    assert status.current_version is None

    database.check_integrity.assert_awaited_once()
    schema.get_version.assert_not_called()


@pytest.mark.asyncio
async def test_database_status_reports_newer_schema(
    tmp_path: Path,
) -> None:
    """Report a database created by a newer Claviger version."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")
        await connection.commit()

    schema = DatabaseSchema(database)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.TOO_NEW
    assert status.current_version == CURRENT_SCHEMA_VERSION + 1


@pytest.mark.asyncio
async def test_database_status_reports_unavailable_database() -> None:
    """Report an existing database that cannot currently be accessed."""
    database = Mock(spec=DatabaseConnection)
    database.exists.return_value = True
    database.check_integrity = AsyncMock(
        side_effect=DatabaseUnavailableError(
            "Database unavailable during integrity inspection."
        )
    )

    schema = Mock(spec=DatabaseSchema)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.UNAVAILABLE
    assert status.current_version is None

    database.check_integrity.assert_awaited_once()
    schema.get_version.assert_not_called()


@pytest.mark.asyncio
async def test_database_status_reports_required_migration(
    tmp_path: Path,
) -> None:
    """Report an existing schema older than the current version."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute("PRAGMA user_version = 1")
        await connection.commit()

    schema = DatabaseSchema(database)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.MIGRATION_REQUIRED
    assert status.current_version == 1
    assert status.target_version == CURRENT_SCHEMA_VERSION
