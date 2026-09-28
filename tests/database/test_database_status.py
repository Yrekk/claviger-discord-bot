from pathlib import Path
from unittest.mock import Mock

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
    DatabaseFindingCode,
    DatabaseState,
    DatabaseStatusService,
)


@pytest.mark.asyncio
async def test_database_status_reports_missing_database(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")
    service = DatabaseStatusService(database, DatabaseSchema(database))

    status = await service.check()

    assert status.state is DatabaseState.MISSING
    assert status.suggested_state is DatabaseState.MISSING
    assert status.current_version is None
    assert status.target_version == CURRENT_SCHEMA_VERSION
    assert status.findings[0].code == DatabaseFindingCode.RESOURCE_MISSING.value


@pytest.mark.asyncio
async def test_existing_empty_database_requires_admin_classification(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")

    async with database.connect():
        pass

    status = await DatabaseStatusService(
        database,
        DatabaseSchema(database),
    ).check()

    assert status.state is None
    assert status.suggested_state is DatabaseState.UNINITIALIZED
    assert status.candidate_states == (
        DatabaseState.UNINITIALIZED,
        DatabaseState.INVALID,
    )
    assert status.requires_administrator_classification is True
    assert status.current_version == 0


@pytest.mark.asyncio
async def test_foreign_tables_suggest_invalid_but_keep_uninitialized_candidate(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")

    async with database.connect() as connection:
        await connection.execute(
            "CREATE TABLE external_data (id INTEGER PRIMARY KEY)"
        )
        await connection.commit()

    status = await DatabaseStatusService(
        database,
        DatabaseSchema(database),
    ).check()

    assert status.state is None
    assert status.suggested_state is DatabaseState.INVALID
    assert status.candidate_states == (
        DatabaseState.UNINITIALIZED,
        DatabaseState.INVALID,
    )
    finding = next(
        finding
        for finding in status.findings
        if finding.code
        == DatabaseFindingCode.NON_APPLICATION_OBJECTS_PRESENT.value
    )
    assert finding.details["object_count"] == 1


@pytest.mark.asyncio
async def test_partial_claviger_schema_without_version_is_invalid_only(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")

    async with database.connect() as connection:
        await connection.execute(
            "CREATE TABLE guild_settings (guild_id INTEGER PRIMARY KEY)"
        )
        await connection.commit()

    status = await DatabaseStatusService(
        database,
        DatabaseSchema(database),
    ).check()

    assert status.state is DatabaseState.INVALID
    assert status.candidate_states == (DatabaseState.INVALID,)


@pytest.mark.asyncio
async def test_database_status_reports_ready_database(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")
    schema = DatabaseSchema(database)

    await schema.initialize()

    status = await DatabaseStatusService(database, schema).check()

    assert status.state is DatabaseState.READY
    assert status.suggested_state is DatabaseState.READY
    assert status.current_version == CURRENT_SCHEMA_VERSION
    assert status.candidate_states == (DatabaseState.READY,)


@pytest.mark.asyncio
async def test_database_status_reports_newer_schema(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")

    async with database.connect() as connection:
        await connection.execute(
            f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}"
        )
        await connection.commit()

    status = await DatabaseStatusService(
        database,
        DatabaseSchema(database),
    ).check()

    assert status.state is DatabaseState.TOO_NEW
    assert status.current_version == CURRENT_SCHEMA_VERSION + 1


@pytest.mark.asyncio
async def test_database_status_reports_unavailable_database() -> None:
    database = Mock(spec=DatabaseConnection)
    path = Mock(spec=Path)
    path.exists.return_value = True
    path.is_file.return_value = True
    database.database_path = path
    database.connect.side_effect = DatabaseUnavailableError("unavailable")

    schema = Mock(spec=DatabaseSchema)

    status = await DatabaseStatusService(database, schema).check()

    assert status.state is DatabaseState.UNAVAILABLE
    assert status.current_version is None


@pytest.mark.asyncio
async def test_database_status_reports_required_migration(
    tmp_path: Path,
) -> None:
    database = DatabaseConnection(tmp_path / "claviger.db")

    async with database.connect() as connection:
        await connection.execute("PRAGMA user_version = 1")
        await connection.commit()

    status = await DatabaseStatusService(
        database,
        DatabaseSchema(database),
    ).check()

    assert status.state is DatabaseState.MIGRATION_REQUIRED
    assert status.current_version == 1
    assert status.target_version == CURRENT_SCHEMA_VERSION
