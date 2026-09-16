from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    DatabaseSchema,
)

pytestmark = pytest.mark.asyncio

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
            await connection.execute(
                GUILD_SETTINGS_V2_SQL,
            )

        if version >= 3:
            await connection.execute(
                GUILD_MEMBER_INTERESTS_V3_SQL,
            )

        if version >= 4:
            await connection.execute(
                GUILD_ADULT_ACCESSES_V4_SQL,
            )

        if version >= 5:
            await connection.execute(
                """
                ALTER TABLE guild_settings
                RENAME COLUMN adult_rules_channel_name
                TO adult_access_channel_name
                """
            )

        if version >= 6:
            for statement in MIGRATIONS[6]:
                await connection.execute(
                    statement,
                )

        if version >= 7:
            for statement in MIGRATIONS[7]:
                await connection.execute(
                    statement,
                )

        if version >= 8:
            for statement in MIGRATIONS[8]:
                await connection.execute(
                    statement,
                )

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


async def _assert_migrates_to_current_version(
    tmp_path: Path,
    historical_version: int,
) -> DatabaseConnection:
    """Create and migrate one historical database."""

    database = DatabaseConnection(
        tmp_path / f"claviger-v{historical_version}.db",
    )

    await _prepare_historical_database(
        database,
        version=historical_version,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION

    return database


async def test_migrate_upgrades_version_one_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate an existing version one database to the current schema."""

    database = await _assert_migrates_to_current_version(
        tmp_path,
        historical_version=1,
    )

    table_names = await _get_table_names(
        database,
    )

    assert {
        "guild_settings",
        "guild_member_interests",
        "guild_adult_accesses",
        "guild_catalogs",
        "guild_workflows",
        "guild_workflow_catalogs",
        "guild_workflow_channels",
    }.issubset(table_names)


async def test_migrate_upgrades_version_two_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version two database to the current schema."""

    database = await _assert_migrates_to_current_version(
        tmp_path,
        historical_version=2,
    )

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_settings)")

        rows = await cursor.fetchall()

    columns = {row[1] for row in rows}

    assert "adult_access_channel_name" in columns
    assert "adult_rules_channel_name" not in columns


async def test_migrate_upgrades_version_three_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version three database to the current schema."""

    database = await _assert_migrates_to_current_version(
        tmp_path,
        historical_version=3,
    )

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_settings)")

        rows = await cursor.fetchall()

    columns = {row[1] for row in rows}

    assert "adult_access_channel_name" in columns
    assert "adult_rules_channel_name" not in columns


async def test_migrate_upgrades_version_four_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Migrate a complete version four database to the current schema."""

    database = await _assert_migrates_to_current_version(
        tmp_path,
        historical_version=4,
    )

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_settings)")

        rows = await cursor.fetchall()

    columns = {row[1] for row in rows}

    assert "adult_access_channel_name" in columns
    assert "adult_rules_channel_name" not in columns


async def test_version_five_migration_preserves_adult_channel_value(
    tmp_path: Path,
) -> None:
    """Preserve the configured adult channel when migrating through version five."""

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


async def test_migrate_upgrades_version_five_database_to_current_schema(
    tmp_path: Path,
) -> None:
    """Add declarative workflow configuration to a version five database."""

    database = await _assert_migrates_to_current_version(
        tmp_path,
        historical_version=5,
    )

    table_names = await _get_table_names(
        database,
    )

    assert {
        "guild_catalogs",
        "guild_workflows",
        "guild_workflow_catalogs",
        "guild_workflow_channels",
    }.issubset(table_names)


async def test_migrate_version_eight_database_to_version_nine_preserves_data(
    tmp_path: Path,
) -> None:
    """Add V9 admin structure fields without losing V8 application data."""

    database = DatabaseConnection(
        tmp_path / "claviger-v8.db",
    )

    await _prepare_historical_database(
        database,
        version=8,
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO database_ownership (
                singleton_id,
                application_id
            )
            VALUES (?, ?)
            """,
            (
                1,
                789,
            ),
        )

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
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                "member",
                "membre",
                "Configure member.",
                "Member",
                "Member workflow.",
                "public",
                "restricted",
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

    table_names = await _get_table_names(
        database,
    )

    assert "guild_admin_configuration" in table_names

    async with database.connect() as connection:
        cursor = await connection.execute("PRAGMA table_info(guild_workflows)")

        workflow_columns = {row[1] for row in await cursor.fetchall()}

        cursor = await connection.execute(
            """
            SELECT
                guild_id,
                workflow_key,
                command_name,
                category_id
            FROM guild_workflows
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        workflow_row = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT application_id
            FROM database_ownership
            WHERE singleton_id = 1
            """
        )

        ownership_row = await cursor.fetchone()

    assert "category_id" in workflow_columns

    assert workflow_row == (
        123,
        "member",
        "membre",
        None,
    )

    assert ownership_row == (789,)
