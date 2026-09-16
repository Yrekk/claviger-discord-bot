from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.migrations.v11_generic_catalogs import (
    MigrationV11DataError,
)
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    DatabaseSchema,
)

pytestmark = pytest.mark.asyncio


async def _prepare_version_ten_database(
    database: DatabaseConnection,
) -> None:
    """Build the exact historical schema immediately preceding V11."""

    async with database.connect() as connection:
        for version in range(
            1,
            11,
        ):
            for statement in MIGRATIONS[version]:
                await connection.execute(
                    statement,
                )

        await connection.execute("PRAGMA user_version = 10")
        await connection.commit()


async def _insert_legacy_fixture(
    database: DatabaseConnection,
) -> None:
    """Populate V10 with duplicate, paired, solo and AI-context examples."""

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                member_interest_prefix,
                adult_access_prefix,
                adult_access_enabled
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                123,
                "interest-",
                "access-",
                1,
            ),
        )

        legacy_interests = (
            (
                401,
                "interest-warhammer",
                "warhammer",
                "Warhammer",
                1,
                1,
            ),
            (
                402,
                "interest-python",
                "python",
                "Python",
                2,
                1,
            ),
            # Same questionnaire key, different role. V11 must keep both
            # targets while presenting one logical questionnaire entry.
            (
                403,
                "interest-python-alt",
                "python",
                "Python",
                3,
                0,
            ),
        )

        for (
            role_id,
            role_name,
            interest_key,
            label,
            sort_order,
            role_manageable,
        ) in legacy_interests:
            await connection.execute(
                """
                INSERT INTO guild_member_interests (
                    guild_id,
                    role_id,
                    role_name,
                    interest_key,
                    channel_id,
                    channel_name,
                    label,
                    sort_order,
                    role_manageable
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    123,
                    role_id,
                    role_name,
                    interest_key,
                    role_id + 1000,
                    f"channel-{role_id}",
                    label,
                    sort_order,
                    role_manageable,
                ),
            )

        legacy_accesses = (
            (
                501,
                "access-no-ia-test",
                "no-ia-test",
                "Test",
                10,
            ),
            (
                502,
                "access-ia-test",
                "ia-test",
                "Test",
                11,
            ),
            (
                503,
                "access-solo",
                "solo",
                "Solo",
                20,
            ),
        )

        for role_id, role_name, access_key, label, sort_order in legacy_accesses:
            await connection.execute(
                """
                INSERT INTO guild_adult_accesses (
                    guild_id,
                    role_id,
                    role_name,
                    access_key,
                    channel_id,
                    channel_name,
                    label,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    123,
                    role_id,
                    role_name,
                    access_key,
                    role_id + 1000,
                    f"channel-{role_id}",
                    label,
                    sort_order,
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
                policy_key
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                "member",
                "membre",
                "Configure member preferences.",
                "Member",
                "public",
            ),
        )

        await connection.execute(
            """
            INSERT INTO guild_context_definitions (
                guild_id,
                context_key,
                capability_key,
                value_type,
                role_id,
                label
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                "ai-preference",
                "ai_preference",
                "boolean",
                900,
                "Préférence IA",
            ),
        )

        await connection.execute(
            """
            INSERT INTO guild_workflow_contexts (
                guild_id,
                workflow_key,
                context_key,
                interaction_mode
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                123,
                "member",
                "ai-preference",
                "editable",
            ),
        )

        await connection.commit()


async def _table_names(
    database: DatabaseConnection,
) -> set[str]:
    """Return every table currently defined in SQLite."""

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )

        rows = await cursor.fetchall()

    return {
        str(row[0])
        for row in rows
    }


async def test_migrate_v10_to_v11_normalizes_legacy_catalogs_and_ai_state(
    tmp_path: Path,
) -> None:
    """Preserve six old role rows as four logical entries and six targets."""

    database = DatabaseConnection(
        tmp_path / "claviger-v10.db",
    )

    await _prepare_version_ten_database(
        database,
    )
    await _insert_legacy_fixture(
        database,
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.migrate()

    assert await schema.get_version() == CURRENT_SCHEMA_VERSION
    assert CURRENT_SCHEMA_VERSION == 11

    table_names = await _table_names(
        database,
    )

    assert "guild_member_interests" not in table_names
    assert "guild_adult_accesses" not in table_names
    assert "guild_catalog_entries" in table_names
    assert "guild_catalog_entry_targets" in table_names

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT ai_enabled, ai_role_id
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (123,),
        )
        settings = await cursor.fetchone()

        cursor = await connection.execute(
            "SELECT COUNT(*) FROM guild_catalog_entries"
        )
        entry_count = await cursor.fetchone()

        cursor = await connection.execute(
            "SELECT COUNT(*) FROM guild_catalog_entry_targets"
        )
        target_count = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT target.role_id, target.variant
            FROM guild_catalog_entry_targets AS target
            INNER JOIN guild_catalog_entries AS entry
                ON entry.guild_id = target.guild_id
               AND entry.catalog_key = target.catalog_key
               AND entry.entry_key = target.entry_key
            WHERE target.guild_id = ?
              AND target.entry_key = ?
            ORDER BY target.role_id
            """,
            (
                123,
                "test",
            ),
        )
        test_targets = await cursor.fetchall()

        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_catalog_entries
            WHERE guild_id = ?
              AND entry_key = ?
            """,
            (
                123,
                "python",
            ),
        )
        python_entries = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_catalog_entry_targets
            WHERE guild_id = ?
              AND role_id = ?
            """,
            (
                123,
                403,
            ),
        )
        non_manageable_target = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_context_definitions
            WHERE capability_key = 'ai_preference'
            """
        )
        legacy_ai_definitions = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_workflow_contexts
            WHERE context_key = 'ai-preference'
            """
        )
        legacy_ai_bindings = await cursor.fetchone()

    assert settings == (
        1,
        900,
    )
    assert entry_count == (4,)
    assert target_count == (6,)
    assert test_targets == [
        (
            501,
            "no_ai",
        ),
        (
            502,
            "ai",
        ),
    ]
    assert python_entries == (1,)
    assert non_manageable_target == (1,)
    assert legacy_ai_definitions == (0,)
    assert legacy_ai_bindings == (0,)


async def test_migrate_v10_preserves_ai_role_when_no_workflow_uses_it(
    tmp_path: Path,
) -> None:
    """Keep the selected role while migrating inactive V10 AI state as disabled."""

    database = DatabaseConnection(
        tmp_path / "claviger-v10-inactive-ai.db",
    )

    await _prepare_version_ten_database(
        database,
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_context_definitions (
                guild_id,
                context_key,
                capability_key,
                value_type,
                role_id,
                label
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                321,
                "ai-preference",
                "ai_preference",
                "boolean",
                901,
                "Préférence IA",
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
            SELECT ai_enabled, ai_role_id
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (321,),
        )
        settings = await cursor.fetchone()

    assert settings == (
        0,
        901,
    )


async def test_migrate_v10_rolls_back_before_dropping_invalid_legacy_data(
    tmp_path: Path,
) -> None:
    """Keep the complete V10 database intact when a legacy key is invalid."""

    database = DatabaseConnection(
        tmp_path / "claviger-v10-invalid.db",
    )

    await _prepare_version_ten_database(
        database,
    )

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_adult_accesses (
                guild_id,
                role_id,
                role_name,
                access_key,
                channel_id,
                channel_name
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                501,
                "access-ia-",
                "ia-",
                1501,
                "invalid",
            ),
        )
        await connection.commit()

    schema = DatabaseSchema(
        database,
    )

    with pytest.raises(
        MigrationV11DataError,
        match="invalid legacy catalog keys",
    ):
        await schema.migrate()

    assert await schema.get_version() == 10

    table_names = await _table_names(
        database,
    )

    assert "guild_member_interests" in table_names
    assert "guild_adult_accesses" in table_names
    assert "guild_catalog_entries" not in table_names
    assert "guild_catalog_entry_targets" not in table_names

    async with database.connect() as connection:
        cursor = await connection.execute(
            "SELECT COUNT(*) FROM guild_adult_accesses"
        )
        legacy_count = await cursor.fetchone()

    assert legacy_count == (1,)
