from pathlib import Path

import aiosqlite
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
async def test_initialize_creates_guild_settings_table(
    tmp_path: Path,
) -> None:
    """Create the guild settings table during schema initialization."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_settings'
            """
        )

        row = await cursor.fetchone()

    assert row == ("guild_settings",)


@pytest.mark.asyncio
async def test_initialize_creates_guild_member_interests_table(
    tmp_path: Path,
) -> None:
    """Create the member interests catalog during schema initialization."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_member_interests'
            """
        )

        row = await cursor.fetchone()

    assert row == ("guild_member_interests",)


@pytest.mark.asyncio
async def test_initialize_creates_guild_adult_accesses_table(
    tmp_path: Path,
) -> None:
    """Create the adult access catalog during schema initialization."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_adult_accesses'
            """
        )

        row = await cursor.fetchone()

    assert row == ("guild_adult_accesses",)


@pytest.mark.asyncio
async def test_migrate_upgrades_version_one_database(
    tmp_path: Path,
) -> None:
    """Migrate an existing version one database to the current schema."""
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute("PRAGMA user_version = 1")
        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_settings'
            """
        )

        row = await cursor.fetchone()

    assert row == ("guild_settings",)


@pytest.mark.asyncio
async def test_migrate_upgrades_version_two_database_to_current_catalogs(
    tmp_path: Path,
) -> None:
    """Apply member interest and adult access migrations to version two."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            CREATE TABLE guild_settings (
                guild_id INTEGER PRIMARY KEY,
                member_role_name TEXT,
                adult_role_name TEXT,
                member_interest_prefix TEXT,
                adult_access_prefix TEXT,
                salutations_channel_name TEXT,
                adult_rules_channel_name TEXT,
                role_management_enabled INTEGER
                    CHECK (
                        role_management_enabled IS NULL
                        OR role_management_enabled IN (0, 1)
                    ),
                adult_access_enabled INTEGER
                    CHECK (
                        adult_access_enabled IS NULL
                        OR adult_access_enabled IN (0, 1)
                    )
            )
            """
        )

        await connection.execute("PRAGMA user_version = 2")

        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN (
                  'guild_member_interests',
                  'guild_adult_accesses'
              )
            ORDER BY name
            """
        )

        rows = await cursor.fetchall()

    assert rows == [
        ("guild_adult_accesses",),
        ("guild_member_interests",),
    ]


@pytest.mark.asyncio
async def test_migrate_upgrades_version_three_database_to_adult_access_catalog(
    tmp_path: Path,
) -> None:
    """Migrate an existing version three database to adult access support."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            CREATE TABLE guild_member_interests (
                guild_id INTEGER NOT NULL,
                role_id INTEGER NOT NULL,

                role_name TEXT NOT NULL,
                interest_key TEXT NOT NULL,

                channel_id INTEGER NOT NULL,
                channel_name TEXT NOT NULL,

                label TEXT,
                description TEXT,
                emoji TEXT,

                sort_order INTEGER NOT NULL DEFAULT 0,

                enabled INTEGER NOT NULL DEFAULT 1
                    CHECK (enabled IN (0, 1)),

                discord_present INTEGER NOT NULL DEFAULT 1
                    CHECK (discord_present IN (0, 1)),

                role_manageable INTEGER NOT NULL DEFAULT 1
                    CHECK (role_manageable IN (0, 1)),

                channel_present INTEGER NOT NULL DEFAULT 1
                    CHECK (channel_present IN (0, 1)),

                mapping_valid INTEGER NOT NULL DEFAULT 1
                    CHECK (mapping_valid IN (0, 1)),

                matches_policy INTEGER NOT NULL DEFAULT 1
                    CHECK (matches_policy IN (0, 1)),

                PRIMARY KEY (guild_id, role_id)
            )
            """
        )

        await connection.execute("PRAGMA user_version = 3")

        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == 4

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'guild_adult_accesses'
            """
        )

        row = await cursor.fetchone()

    assert row == ("guild_adult_accesses",)


@pytest.mark.asyncio
async def test_member_interests_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete member interests catalog schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_member_interests)")

        rows = await cursor.fetchall()

    column_names = {row[1] for row in rows}

    assert column_names == {
        "guild_id",
        "role_id",
        "role_name",
        "interest_key",
        "channel_id",
        "channel_name",
        "label",
        "description",
        "emoji",
        "sort_order",
        "enabled",
        "discord_present",
        "role_manageable",
        "channel_present",
        "mapping_valid",
        "matches_policy",
    }


@pytest.mark.asyncio
async def test_adult_accesses_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete adult access catalog schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_adult_accesses)")

        rows = await cursor.fetchall()

    column_names = {row[1] for row in rows}

    assert column_names == {
        "guild_id",
        "role_id",
        "role_name",
        "access_key",
        "channel_id",
        "channel_name",
        "label",
        "description",
        "emoji",
        "sort_order",
        "enabled",
        "discord_present",
        "role_manageable",
        "channel_present",
        "mapping_valid",
        "matches_policy",
    }


@pytest.mark.asyncio
async def test_member_interest_requires_channel_mapping(
    tmp_path: Path,
) -> None:
    """Reject member interests without a Discord channel mapping."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        with pytest.raises(aiosqlite.IntegrityError):
            await connection.execute(
                """
                INSERT INTO guild_member_interests (
                    guild_id,
                    role_id,
                    role_name,
                    interest_key
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    123,
                    456,
                    "interest-ludus",
                    "ludus",
                ),
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_adult_access_requires_channel_mapping(
    tmp_path: Path,
) -> None:
    """Reject adult accesses without a Discord channel mapping."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_adult_accesses (
                    guild_id,
                    role_id,
                    role_name,
                    access_key
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    123,
                    456,
                    "access-ia-futa",
                    "ia-futa",
                ),
            )

        await connection.rollback()
