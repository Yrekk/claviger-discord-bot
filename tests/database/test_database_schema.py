from pathlib import Path

import aiosqlite
import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    DatabaseSchema,
    UnsupportedSchemaVersionError,
)


GUILD_SETTINGS_V2_SQL = """
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


GUILD_MEMBER_INTERESTS_V3_SQL = """
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


GUILD_ADULT_ACCESSES_V4_SQL = """
CREATE TABLE guild_adult_accesses (
    guild_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,

    role_name TEXT NOT NULL,
    access_key TEXT NOT NULL,

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


async def _prepare_historical_database(
    database: DatabaseConnection,
    version: int,
) -> None:
    """Create a complete historical database schema for the requested version."""

    async with database.connect() as connection:
        if version >= 2:
            await connection.execute(GUILD_SETTINGS_V2_SQL)

        if version >= 3:
            await connection.execute(GUILD_MEMBER_INTERESTS_V3_SQL)

        if version >= 4:
            await connection.execute(GUILD_ADULT_ACCESSES_V4_SQL)

        await connection.execute(f"PRAGMA user_version = {version}")
        await connection.commit()


async def _get_table_names(
    database: DatabaseConnection,
) -> set[str]:
    """Return every user-defined SQLite table name."""

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        rows = await cursor.fetchall()

    return {row[0] for row in rows}


async def _get_column_names(
    database: DatabaseConnection,
    table_name: str,
) -> set[str]:
    """Return the column names for one SQLite table."""

    async with database.connect() as connection:
        cursor = await connection.execute(f"PRAGMA table_info({table_name})")

        rows = await cursor.fetchall()

    return {row[1] for row in rows}


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


@pytest.mark.asyncio
async def test_initialize_creates_expected_tables(
    tmp_path: Path,
) -> None:
    """Create every table required by the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    table_names = await _get_table_names(database)

    assert {
        "guild_settings",
        "guild_member_interests",
        "guild_adult_accesses",
    }.issubset(table_names)


@pytest.mark.asyncio
async def test_migrate_upgrades_version_one_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate an existing version one database to the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await _prepare_historical_database(
        database,
        version=1,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    table_names = await _get_table_names(database)

    assert {
        "guild_settings",
        "guild_member_interests",
        "guild_adult_accesses",
    }.issubset(table_names)


@pytest.mark.asyncio
async def test_migrate_upgrades_version_two_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version two database to the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await _prepare_historical_database(
        database,
        version=2,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    table_names = await _get_table_names(database)

    assert {
        "guild_settings",
        "guild_member_interests",
        "guild_adult_accesses",
    }.issubset(table_names)

    column_names = await _get_column_names(
        database,
        "guild_settings",
    )

    assert "adult_access_channel_name" in column_names
    assert "adult_rules_channel_name" not in column_names


@pytest.mark.asyncio
async def test_migrate_upgrades_version_three_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version three database to the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await _prepare_historical_database(
        database,
        version=3,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    table_names = await _get_table_names(database)

    assert {
        "guild_settings",
        "guild_member_interests",
        "guild_adult_accesses",
    }.issubset(table_names)

    column_names = await _get_column_names(
        database,
        "guild_settings",
    )

    assert "adult_access_channel_name" in column_names
    assert "adult_rules_channel_name" not in column_names


@pytest.mark.asyncio
async def test_migrate_upgrades_version_four_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version four database to the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await _prepare_historical_database(
        database,
        version=4,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    column_names = await _get_column_names(
        database,
        "guild_settings",
    )

    assert "adult_access_channel_name" in column_names
    assert "adult_rules_channel_name" not in column_names


@pytest.mark.asyncio
async def test_version_five_migration_preserves_adult_channel_value(
    tmp_path: Path,
) -> None:
    """Preserve the configured adult channel when renaming its column."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await _prepare_historical_database(
        database,
        version=4,
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                adult_rules_channel_name
            )
            VALUES (?, ?)
            """,
            (
                123,
                "adult-validation",
            ),
        )
        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT adult_access_channel_name
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (123,),
        )

        row = await cursor.fetchone()

    assert row == ("adult-validation",)


@pytest.mark.asyncio
async def test_guild_settings_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete current guild settings schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    column_names = await _get_column_names(
        database,
        "guild_settings",
    )

    assert column_names == {
        "guild_id",
        "member_role_name",
        "adult_role_name",
        "member_interest_prefix",
        "adult_access_prefix",
        "salutations_channel_name",
        "adult_access_channel_name",
        "role_management_enabled",
        "adult_access_enabled",
    }


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

    column_names = await _get_column_names(
        database,
        "guild_member_interests",
    )

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

    column_names = await _get_column_names(
        database,
        "guild_adult_accesses",
    )

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
        with pytest.raises(aiosqlite.IntegrityError):
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
                    "access-ia-test",
                    "ia-test",
                ),
            )

        await connection.rollback()
