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
