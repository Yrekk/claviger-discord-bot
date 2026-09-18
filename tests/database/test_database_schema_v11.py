"""Exercise real SQLite upgrades, conservation and rollback without Discord."""

import asyncio
import sqlite3
from pathlib import Path

import aiosqlite
import pytest

from claviger.database import migration_v11
from claviger.database import schema as schema_module
from claviger.database.connection import DatabaseConnection
from claviger.database.migration_v11 import LegacyCatalogMigrationError
from claviger.database.schema import CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseSchema

pytestmark = pytest.mark.asyncio


async def _historical(tmp_path: Path, version: int = 10) -> DatabaseConnection:
    """Build a historical schema without invoking the current initializer."""

    database = DatabaseConnection(tmp_path / "historical.db")
    async with database.connect() as connection:
        for step in range(1, version + 1):
            for statement in MIGRATIONS[step]:
                await connection.execute(statement)
        await connection.execute(f"PRAGMA user_version = {version}")
        await connection.commit()
    return database


async def _rows(database: DatabaseConnection, sql: str) -> list[tuple]:
    """Read persisted results through a new connection after commit/rollback."""

    async with database.connect() as connection:
        async with connection.execute(sql) as cursor:
            return await cursor.fetchall()


async def _insert(
    database: DatabaseConnection,
    table: str = "guild_adult_accesses",
    **values,
) -> None:
    """Insert one representative historical row; SQL identifiers are test-owned."""

    key_column = "access_key" if table == "guild_adult_accesses" else "interest_key"
    values.setdefault("guild_id", 123)
    values.setdefault("role_id", 501)
    values.setdefault(key_column, "no-ia-fantasy")
    prefix = "access-" if table == "guild_adult_accesses" else "interest-"
    values.setdefault("role_name", prefix + values[key_column])
    values.setdefault("channel_id", values["role_id"] + 1000)
    values.setdefault("channel_name", "channel")
    async with database.connect() as connection:
        await connection.execute(
            f"INSERT INTO {table} ({', '.join(values)}) "
            f"VALUES ({', '.join('?' for _ in values)})",
            tuple(values.values()),
        )
        await connection.commit()


async def _execute(
    database: DatabaseConnection, sql: str, parameters: tuple = ()
) -> None:
    """Commit fixture setup independently of the migration transaction."""

    async with database.connect() as connection:
        await connection.execute(sql, parameters)
        await connection.commit()


async def _context(
    database: DatabaseConnection,
    guild_id: int = 123,
    role_id: int = 900,
    enabled: int = 1,
) -> None:
    """Seed the former explicit guild-wide AI preference identity."""

    await _execute(
        database,
        """
        INSERT INTO guild_context_definitions
            (guild_id, context_key, capability_key, value_type, role_id, label, enabled)
        VALUES (?, 'shared-ai', 'ai_preference', 'boolean', ?, 'IA', ?)
        """,
        (guild_id, role_id, enabled),
    )


def _dump(database: DatabaseConnection) -> str:
    """Capture all schema and rows to prove rollback, not just the version flag."""

    with sqlite3.connect(database.database_path) as connection:
        return "\n".join(connection.iterdump())


async def _unexpected(*args, **kwargs):
    """Fail a test if an unnecessary historical probe or conversion is called."""

    raise AssertionError("Unexpected historical data operation")


@pytest.mark.parametrize("version", range(1, 11))
async def test_all_supported_versions_reach_current_schema(
    tmp_path: Path,
    version: int,
) -> None:
    """Keep each supported upgrade path through V11 conversion to current schema."""

    database = await _historical(tmp_path, version)
    await DatabaseSchema(database).migrate()

    assert await DatabaseSchema(database).get_version() == CURRENT_SCHEMA_VERSION

    names = {
        row[0]
        for row in await _rows(
            database, "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"guild_catalog_entries", "guild_catalog_entry_targets"} <= names
    assert not {"guild_member_interests", "guild_adult_accesses"} & names

    guild_settings_columns = [
        row[1]
        for row in await _rows(database, "PRAGMA table_info(guild_settings)")
    ]
    assert guild_settings_columns == ["guild_id", "ai_enabled", "ai_role_id"]


async def test_fresh_database_never_probes_or_recovers_legacy_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A known-new installation must not attempt historical catalog recovery."""

    monkeypatch.setattr(migration_v11, "_has_rows", _unexpected)
    monkeypatch.setattr(migration_v11, "_copy_legacy_catalog", _unexpected)

    database = DatabaseConnection(tmp_path / "new.db")
    await DatabaseSchema(database).initialize()

    assert await DatabaseSchema(database).get_version() == CURRENT_SCHEMA_VERSION
    assert await _rows(database, "SELECT * FROM guild_settings") == []
    assert await _rows(database, "SELECT * FROM guild_catalogs") == []


async def test_empty_historical_database_skips_conversion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EXISTS checks must prevent loading/converting empty historical sources."""

    database = await _historical(tmp_path)
    monkeypatch.setattr(migration_v11, "_copy_legacy_catalog", _unexpected)

    await DatabaseSchema(database).migrate()

    assert await _rows(database, "SELECT * FROM guild_catalog_entries") == []


async def test_only_nonempty_source_is_converted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty second catalog must not invoke its converter."""

    database = await _historical(tmp_path)
    await _insert(database, "guild_member_interests", interest_key="coding")
    original = migration_v11._copy_legacy_catalog
    calls = []

    async def record(connection, source):
        calls.append(source.table)
        return await original(connection, source)

    monkeypatch.setattr(migration_v11, "_copy_legacy_catalog", record)

    await DatabaseSchema(database).migrate()

    assert calls == ["guild_member_interests"]


async def test_pair_uses_no_ai_metadata_and_preserves_both_targets(
    tmp_path: Path,
) -> None:
    """Different AI metadata must not block migration or override no-AI display."""

    database = await _historical(tmp_path)
    await _insert(
        database,
        access_key="no-ia-fantasy",
        label="Fantasy",
        description="Original",
        emoji="✨",
        sort_order=4,
    )
    await _insert(
        database,
        role_id=502,
        access_key="ia-fantasy",
        label="Other",
        description="Different",
        emoji="🤖",
        sort_order=9,
        enabled=0,
        discord_present=0,
        role_manageable=0,
        channel_present=0,
        mapping_valid=0,
        matches_policy=0,
    )

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database,
        """
        SELECT entry_key, label, description, emoji, sort_order, enabled
        FROM guild_catalog_entries
        """,
    ) == [("fantasy", "Fantasy", "Original", "✨", 4, 1)]
    assert await _rows(
        database,
        """
        SELECT role_id, variant, enabled, discord_present, role_manageable,
               channel_present, mapping_valid, matches_policy
        FROM guild_catalog_entry_targets ORDER BY role_id
        """,
    ) == [(501, "no_ai", 1, 1, 1, 1, 1, 1), (502, "ai", 0, 0, 0, 0, 0, 0)]
    assert await _rows(database, "SELECT * FROM guild_settings") == []


async def test_empty_no_ai_metadata_does_not_fall_back_to_ai(tmp_path: Path) -> None:
    """No-AI remains authoritative even when the AI variant is more decorated."""

    database = await _historical(tmp_path)
    await _insert(database, label=None, description="", emoji=None, enabled=0)
    await _insert(
        database,
        role_id=502,
        access_key="ia-fantasy",
        label="AI",
        description="Text",
        emoji="🤖",
        enabled=1,
    )

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database,
        """
        SELECT label, description, emoji, enabled FROM guild_catalog_entries
        """,
    ) == [(None, "", None, 0)]


@pytest.mark.parametrize(
    "key,entry,variant",
    [
        ("special", "special", "base"),
        ("special-extra", "special-extra", "base"),
        ("ia-images", "images", "ai"),
        ("no-ia-images", "images", "no_ai"),
    ],
)
async def test_singletons_preserve_metadata_without_inventing_emojis(
    tmp_path: Path,
    key: str,
    entry: str,
    variant: str,
) -> None:
    """access-special stays in access; AI-only markers belong to presentation."""

    database = await _historical(tmp_path)
    await _insert(database, access_key=key, label="Choice", emoji=None)

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database, "SELECT entry_key, label, emoji FROM guild_catalog_entries"
    ) == [(entry, "Choice", None)]
    assert await _rows(database, "SELECT variant FROM guild_catalog_entry_targets") == [
        (variant,)
    ]


async def test_interest_named_ia_remains_an_ordinary_interest(tmp_path: Path) -> None:
    """Historical interests in AI are not an AI-content preference or variant."""

    database = await _historical(tmp_path)
    await _insert(database, "guild_member_interests", interest_key="ia")

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database, "SELECT entry_key, variant FROM guild_catalog_entry_targets"
    ) == [("ia", "base")]
    assert await _rows(database, "SELECT * FROM guild_settings") == []


async def test_v5_policy_fields_feed_conversion_then_are_retired(
    tmp_path: Path,
) -> None:
    """Use legacy prefixes during conversion without keeping V1 policy columns."""

    database = await _historical(tmp_path, 5)
    await _execute(
        database,
        """
        INSERT INTO guild_settings (guild_id, adult_access_prefix, adult_role_name)
        VALUES (123, 'themes-', 'Existing role')
        """,
    )
    await _insert(database, access_key="ia-art", role_name="themes-ia-art")
    await _insert(
        database, "guild_member_interests", role_id=600, interest_key="cuisine"
    )

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database,
        "SELECT guild_id, ai_enabled, ai_role_id FROM guild_settings",
    ) == [(123, None, None)]
    assert await _rows(
        database, "SELECT role_prefix FROM guild_catalogs ORDER BY role_prefix"
    ) == [("interest-",), ("themes-",)]
    assert await _rows(database, "SELECT * FROM guild_workflows") == []
    assert len(await _rows(database, "SELECT * FROM guild_catalog_entry_targets")) == 2


async def test_reuses_existing_catalog_and_preserves_workflow_bindings(
    tmp_path: Path,
) -> None:
    """Never replace human catalog metadata or silently invent another binding."""

    database = await _historical(tmp_path)
    await _execute(
        database,
        """
        INSERT INTO guild_catalogs
            (guild_id, catalog_key, role_prefix, display_name, entry_name, enabled)
        VALUES (123, 'chosen-key', 'access-', 'Custom catalog', 'Theme', 0)
        """,
    )
    await _execute(
        database,
        """
        INSERT INTO guild_workflows
            (guild_id, workflow_key, command_name, command_description, title, policy_key)
        VALUES (123, 'custom', 'custom', 'Description', 'Custom workflow', 'public')
        """,
    )
    await _execute(
        database,
        """
        INSERT INTO guild_workflow_catalogs (guild_id, workflow_key, catalog_key)
        VALUES (123, 'custom', 'chosen-key')
        """,
    )
    before = await _rows(database, "SELECT * FROM guild_workflow_catalogs")
    await _insert(database)

    await DatabaseSchema(database).migrate()

    assert await _rows(database, "SELECT catalog_key FROM guild_catalog_entries") == [
        ("chosen-key",)
    ]
    assert await _rows(
        database, "SELECT display_name, enabled FROM guild_catalogs"
    ) == [("Custom catalog", 0)]
    assert await _rows(database, "SELECT * FROM guild_workflow_catalogs") == before


async def test_guilds_are_isolated_and_ownership_is_preserved(tmp_path: Path) -> None:
    """Group by guild as well as key; retain application ownership unchanged."""

    database = await _historical(tmp_path)
    await _execute(database, "INSERT INTO database_ownership VALUES (1, 9000)")
    await _insert(database, guild_id=123, label="A")
    await _insert(database, guild_id=456, label="B")

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database, "SELECT guild_id, label FROM guild_catalog_entries ORDER BY guild_id"
    ) == [(123, "A"), (456, "B")]
    assert await _rows(database, "SELECT * FROM database_ownership") == [(1, 9000)]


@pytest.mark.parametrize("enabled", [0, 1])
async def test_legacy_ai_context_is_retired_without_carrying_state(
    tmp_path: Path,
    enabled: int,
) -> None:
    """V11 starts AI configuration clean instead of inheriting workflow state."""

    database = await _historical(tmp_path)
    await _context(database, enabled=enabled)

    await DatabaseSchema(database).migrate()

    assert await _rows(database, "SELECT * FROM guild_settings") == []
    assert await _rows(
        database,
        "SELECT role_id FROM guild_context_definitions WHERE capability_key = 'ai_preference'",
    ) == []


async def test_unconfigured_guild_stays_distinct_from_ai_disabled(
    tmp_path: Path,
) -> None:
    """Existing V1 configuration alone does not answer the V11 AI setup question."""

    database = await _historical(tmp_path)
    await _execute(
        database,
        "INSERT INTO guild_settings (guild_id, adult_access_enabled) VALUES (123, 1)",
    )

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database, "SELECT ai_enabled, ai_role_id FROM guild_settings"
    ) == [(None, None)]


@pytest.mark.parametrize("bad_key", ["", "ia-", "no-ia-", " space "])
async def test_invalid_key_rolls_back_schema_data_and_version(
    tmp_path: Path,
    bad_key: str,
) -> None:
    """Invalid migration input must leave the whole V10 database unchanged."""

    database = await _historical(tmp_path)
    await _insert(database, access_key=bad_key)
    before = _dump(database)

    with pytest.raises(LegacyCatalogMigrationError):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before
    assert await DatabaseSchema(database).get_version() == 10


@pytest.mark.parametrize("second_key", ["no-ia-fantasy", "fantasy"])
async def test_duplicate_or_colliding_logical_keys_fail_closed(
    tmp_path: Path,
    second_key: str,
) -> None:
    """Do not merge duplicate variants or ambiguous singleton/variant shapes."""

    database = await _historical(tmp_path)
    await _insert(database)
    await _insert(database, role_id=502, access_key=second_key)
    before = _dump(database)

    with pytest.raises(LegacyCatalogMigrationError):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before


async def test_same_role_in_two_historical_catalogs_is_rejected(tmp_path: Path) -> None:
    """A single guild role cannot acquire two different catalog owners."""

    database = await _historical(tmp_path)
    await _insert(database)
    await _insert(database, "guild_member_interests", interest_key="coding")
    before = _dump(database)

    with pytest.raises(aiosqlite.IntegrityError):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before


@pytest.mark.parametrize("prefix", ["access-special-", "access"])
async def test_overlapping_configured_prefixes_fail_closed(
    tmp_path: Path,
    prefix: str,
) -> None:
    """Do not silently choose between nested catalog prefixes."""

    database = await _historical(tmp_path)
    await _execute(
        database,
        """
        INSERT INTO guild_catalogs (guild_id, catalog_key, role_prefix, display_name, entry_name)
        VALUES (123, 'existing', ?, 'Existing', 'Choice')
        """,
        (prefix,),
    )
    await _insert(database)
    before = _dump(database)

    with pytest.raises(LegacyCatalogMigrationError, match="prefix"):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before


async def test_legacy_ai_role_can_become_catalog_target_after_context_retirement(
    tmp_path: Path,
) -> None:
    """The old workflow AI identity is not reserved by the new guild AI model."""

    database = await _historical(tmp_path)
    await _context(database, role_id=501)
    await _insert(database)

    await DatabaseSchema(database).migrate()

    assert await _rows(
        database,
        "SELECT role_id FROM guild_catalog_entry_targets",
    ) == [(501,)]
    assert await _rows(
        database,
        "SELECT role_id FROM guild_context_definitions WHERE capability_key = 'ai_preference'",
    ) == []


@pytest.mark.parametrize(
    "exception_type",
    [RuntimeError, ValueError, asyncio.CancelledError],
)
async def test_failure_after_source_removal_restores_everything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exception_type: type[BaseException],
) -> None:
    """Even late migration failure must restore the complete V10 database."""

    database = await _historical(tmp_path)
    await _insert(database)
    before = _dump(database)
    original = schema_module.migrate_v11_data

    async def fail_after_drop(connection, **kwargs):
        await original(connection, **kwargs)
        raise exception_type("Injected interruption")

    monkeypatch.setattr(schema_module, "migrate_v11_data", fail_after_drop)

    with pytest.raises(exception_type):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before
    assert await DatabaseSchema(database).get_version() == 10

    monkeypatch.setattr(schema_module, "migrate_v11_data", original)
    await DatabaseSchema(database).migrate()

    assert await DatabaseSchema(database).get_version() == CURRENT_SCHEMA_VERSION


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO guild_settings (guild_id, ai_enabled) VALUES (123, 2)",
        "INSERT INTO guild_settings (guild_id, ai_role_id) VALUES (123, 0)",
        "INSERT INTO guild_settings (guild_id, ai_role_id) VALUES (123, -1)",
    ],
)
async def test_ai_setting_constraints(tmp_path: Path, sql: str) -> None:
    """Reject non-boolean activation and invalid Discord identities."""

    database = DatabaseConnection(tmp_path / "new.db")
    await DatabaseSchema(database).initialize()

    with pytest.raises(aiosqlite.IntegrityError):
        await _execute(database, sql)


async def test_unknown_ai_state_and_explicit_false_are_both_supported(
    tmp_path: Path,
) -> None:
    """Unconfigured, disabled and enabled-without-role remain distinct states."""

    database = DatabaseConnection(tmp_path / "new.db")
    await DatabaseSchema(database).initialize()

    for guild, enabled in [(1, None), (2, 0), (3, 1)]:
        await _execute(
            database,
            "INSERT INTO guild_settings (guild_id, ai_enabled) VALUES (?, ?)",
            (guild, enabled),
        )

    assert await _rows(
        database, "SELECT ai_enabled, ai_role_id FROM guild_settings ORDER BY guild_id"
    ) == [(None, None), (0, None), (1, None)]


async def test_future_schema_is_rejected_without_any_mutation(tmp_path: Path) -> None:
    """An application upgrade must not downgrade a database from the future."""

    database = await _historical(tmp_path)
    await _execute(
        database,
        f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}",
    )
    before = _dump(database)

    with pytest.raises(schema_module.UnsupportedSchemaVersionError):
        await DatabaseSchema(database).migrate()

    assert _dump(database) == before
