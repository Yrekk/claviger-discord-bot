from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema

pytestmark = pytest.mark.asyncio


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
    """Return the columns defined by one SQLite table."""

    async with database.connect() as connection:
        cursor = await connection.execute(f"PRAGMA table_info({table_name})")

        rows = await cursor.fetchall()

    return {row[1] for row in rows}


async def _create_database(
    tmp_path: Path,
) -> DatabaseConnection:
    """Create one database using the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return database


async def test_initialize_creates_expected_tables(
    tmp_path: Path,
) -> None:
    """Create every table required by the current schema."""

    database = await _create_database(
        tmp_path,
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
        "guild_context_definitions",
        "guild_workflow_contexts",
    }.issubset(table_names)


async def test_guild_settings_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete current guild settings schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_settings",
    ) == {
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


async def test_member_interests_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete legacy member interests catalog schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_member_interests",
    ) == {
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


async def test_adult_accesses_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the complete legacy adult access catalog schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_adult_accesses",
    ) == {
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


async def test_catalog_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the declarative catalog definition schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_catalogs",
    ) == {
        "guild_id",
        "catalog_key",
        "role_prefix",
        "display_name",
        "entry_name",
        "description",
        "sort_order",
        "enabled",
    }


async def test_workflow_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the declarative workflow definition schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_workflows",
    ) == {
        "guild_id",
        "workflow_key",
        "command_name",
        "command_description",
        "title",
        "description",
        "policy_key",
        "channel_mode",
        "sort_order",
        "enabled",
    }


async def test_workflow_catalog_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the workflow-to-catalog binding schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_workflow_catalogs",
    ) == {
        "guild_id",
        "workflow_key",
        "catalog_key",
        "policy_key",
        "sort_order",
        "enabled",
    }


async def test_workflow_channel_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Store workflow channel routing using Discord IDs."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_workflow_channels",
    ) == {
        "guild_id",
        "workflow_key",
        "channel_id",
    }


async def test_context_definition_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the declarative workflow context definition schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_context_definitions",
    ) == {
        "guild_id",
        "context_key",
        "capability_key",
        "value_type",
        "role_id",
        "label",
        "description",
        "sort_order",
        "enabled",
    }


async def test_workflow_context_table_has_expected_columns(
    tmp_path: Path,
) -> None:
    """Create the workflow-to-context binding schema."""

    database = await _create_database(
        tmp_path,
    )

    assert await _get_column_names(
        database,
        "guild_workflow_contexts",
    ) == {
        "guild_id",
        "workflow_key",
        "context_key",
        "interaction_mode",
        "sort_order",
        "enabled",
    }
