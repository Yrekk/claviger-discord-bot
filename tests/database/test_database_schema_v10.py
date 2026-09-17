from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    DatabaseSchema,
)

pytestmark = pytest.mark.asyncio


async def _prepare_version_nine_database(
    database: DatabaseConnection,
) -> None:
    """Build the exact historical schema immediately preceding V10."""

    async with database.connect() as connection:
        # Replaying the versioned migration registry keeps this fixture aligned
        # with the real historical schema instead of maintaining another SQL copy.
        for version in range(
            1,
            10,
        ):
            for statement in MIGRATIONS[version]:
                await connection.execute(
                    statement,
                )

        await connection.execute("PRAGMA user_version = 9")

        await connection.commit()


async def test_migrate_version_nine_adds_workflow_resource_identities(
    tmp_path: Path,
) -> None:
    """Add V10 workflow structure columns without losing existing workflow data."""

    database = DatabaseConnection(
        tmp_path / "claviger-v9.db",
    )

    await _prepare_version_nine_database(
        database,
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_workflows (
                guild_id,
                workflow_key,
                command_name,
                command_description,
                title,
                description,
                policy_key,
                channel_mode,
                category_id,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                "member",
                "membre",
                "Configure member.",
                "Member",
                "Existing workflow.",
                "public",
                "restricted",
                100,
                10,
                1,
            ),
        )

        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_workflows)")

        columns = {row[1] for row in await cursor.fetchall()}

        cursor = await connection.execute(
            """
            SELECT
                workflow_key,
                policy_key,
                category_id,
                management_channel_id,
                primary_role_id
            FROM guild_workflows
            WHERE guild_id = ?
            """,
            (123,),
        )

        row = await cursor.fetchone()

    assert "management_channel_id" in columns
    assert "primary_role_id" in columns

    # Historical workflow semantics remain untouched by the migration.
    assert row == (
        "member",
        "public",
        100,
        None,
        None,
    )

