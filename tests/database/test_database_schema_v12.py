import sqlite3
from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import CURRENT_SCHEMA_VERSION, DatabaseSchema

pytestmark = pytest.mark.asyncio


async def test_schema_v12_creates_unique_ai_questionnaire_owner_table(
    tmp_path: Path,
) -> None:
    """Persist one owner pointer per guild with workflow referential integrity."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION == 12

    with sqlite3.connect(database.database_path) as connection:
        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(guild_ai_questionnaire_owner)"
            ).fetchall()
        ]

    assert columns == [
        "guild_id",
        "workflow_key",
    ]



async def test_schema_v11_database_migrates_to_v12_owner_table(
    tmp_path: Path,
) -> None:
    """Upgrade an already-current V11 development database without rebuilding it."""

    database = DatabaseConnection(
        tmp_path / "v11.db",
    )
    schema = DatabaseSchema(
        database,
    )

    database.database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with database.connect() as connection:
        for version in range(
            1,
            12,
        ):
            await schema._apply_migration(
                connection,
                version,
                transfer_legacy_data=False,
            )

    assert await schema.get_version() == 11

    await schema.migrate()

    assert await schema.get_version() == 12

    with sqlite3.connect(database.database_path) as connection:
        table = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_ai_questionnaire_owner'
            """
        ).fetchone()

    assert table == (
        "guild_ai_questionnaire_owner",
    )
