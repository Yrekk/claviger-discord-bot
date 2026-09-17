"""Regression coverage for real V10 adult-access shapes observed in DEV."""

from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import MIGRATIONS, DatabaseSchema

pytestmark = pytest.mark.asyncio


async def _historical_v10(tmp_path: Path) -> DatabaseConnection:
    """Build a V10 database without invoking the current initializer."""

    database = DatabaseConnection(tmp_path / "historical.db")
    async with database.connect() as connection:
        for step in range(1, 11):
            for statement in MIGRATIONS[step]:
                await connection.execute(statement)
        await connection.execute("PRAGMA user_version = 10")
        await connection.commit()
    return database


async def _insert_access(
    database: DatabaseConnection,
    *,
    role_id: int,
    access_key: str,
    label: str,
) -> None:
    """Insert one representative historical adult-access row."""

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_adult_accesses
                (guild_id, role_id, role_name, access_key, channel_id,
                 channel_name, label, description)
            VALUES (123, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                role_id,
                f"access-{access_key}",
                access_key,
                role_id + 1000,
                f"channel-{access_key}",
                label,
                label,
            ),
        )
        await connection.commit()


async def _rows(database: DatabaseConnection, sql: str) -> list[tuple]:
    """Read committed migration results."""

    async with database.connect() as connection:
        async with connection.execute(sql) as cursor:
            return await cursor.fetchall()


async def test_plain_access_and_ai_pair_with_same_theme_both_survive_v11(
    tmp_path: Path,
) -> None:
    """Keep generic access separate from the no-AI/AI family sharing its suffix."""

    database = await _historical_v10(tmp_path)
    await _insert_access(database, role_id=501, access_key="test", label="Generic")
    await _insert_access(
        database,
        role_id=502,
        access_key="no-ia-test",
        label="Variant",
    )
    await _insert_access(
        database,
        role_id=503,
        access_key="ia-test",
        label="Variant",
    )

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database,
        """
        SELECT entry_key, label
        FROM guild_catalog_entries
        ORDER BY entry_key
        """,
    ) == [
        ("test", "Generic"),
        ("test--ai-variants", "Variant"),
    ]
    assert await _rows(
        database,
        """
        SELECT role_id, entry_key, variant
        FROM guild_catalog_entry_targets
        ORDER BY role_id
        """,
    ) == [
        (501, "test", "base"),
        (502, "test--ai-variants", "no_ai"),
        (503, "test--ai-variants", "ai"),
    ]
