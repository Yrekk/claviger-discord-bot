from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.connection import DatabaseConnection
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
async def test_database_status_reports_newer_schema(
    tmp_path: Path,
) -> None:
    """Report a database created by a newer Claviger version."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(
            f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}"
        )
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
    database.is_available = AsyncMock(return_value=False)

    schema = Mock(spec=DatabaseSchema)

    service = DatabaseStatusService(
        database,
        schema,
    )

    status = await service.check()

    assert status.state is DatabaseState.UNAVAILABLE
    assert status.current_version is None

    schema.get_version.assert_not_called()