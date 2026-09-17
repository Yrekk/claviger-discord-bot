"""Convert historical catalogs into generic entries and Discord targets.

Only this migration interprets the former member/adult storage conventions.
It never contacts Discord, grants roles, or invents workflow bindings. Its caller
owns the transaction, including DDL, source removal and PRAGMA user_version.
"""

from collections import defaultdict
from dataclasses import dataclass

import aiosqlite

from claviger.services.catalogs.catalog_variant_classifier import (
    CatalogVariantClassifier,
)


class LegacyCatalogMigrationError(RuntimeError):
    """Reject historical data that cannot be converted without ambiguity."""


MIGRATION_11_STATEMENTS: tuple[str, ...] = (
    """
    ALTER TABLE guild_settings ADD COLUMN ai_enabled INTEGER
        CHECK (ai_enabled IS NULL OR ai_enabled IN (0, 1))
    """,
    """
    ALTER TABLE guild_settings ADD COLUMN ai_role_id INTEGER
        CHECK (ai_role_id IS NULL OR ai_role_id > 0)
    """,
    """
    CREATE TABLE guild_catalog_entries (
        guild_id INTEGER NOT NULL CHECK (guild_id > 0),
        catalog_key TEXT NOT NULL,
        entry_key TEXT NOT NULL CHECK (length(trim(entry_key)) > 0),
        label TEXT,
        description TEXT,
        emoji TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        PRIMARY KEY (guild_id, catalog_key, entry_key),
        FOREIGN KEY (guild_id, catalog_key)
            REFERENCES guild_catalogs (guild_id, catalog_key)
            ON UPDATE CASCADE ON DELETE RESTRICT
    )
    """,
    """
    CREATE TABLE guild_catalog_entry_targets (
        guild_id INTEGER NOT NULL CHECK (guild_id > 0),
        catalog_key TEXT NOT NULL,
        entry_key TEXT NOT NULL,
        role_id INTEGER NOT NULL CHECK (role_id > 0),
        role_name TEXT NOT NULL,
        channel_id INTEGER NOT NULL CHECK (channel_id > 0),
        channel_name TEXT NOT NULL,
        variant TEXT NOT NULL CHECK (variant IN ('base', 'no_ai', 'ai')),
        enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
        discord_present INTEGER NOT NULL DEFAULT 1
            CHECK (discord_present IN (0, 1)),
        role_manageable INTEGER NOT NULL DEFAULT 1
            CHECK (role_manageable IN (0, 1)),
        channel_present INTEGER NOT NULL DEFAULT 1
            CHECK (channel_present IN (0, 1)),
        mapping_valid INTEGER NOT NULL DEFAULT 1 CHECK (mapping_valid IN (0, 1)),
        matches_policy INTEGER NOT NULL DEFAULT 1 CHECK (matches_policy IN (0, 1)),
        PRIMARY KEY (guild_id, role_id),
        UNIQUE (guild_id, catalog_key, entry_key, variant),
        FOREIGN KEY (guild_id, catalog_key, entry_key)
            REFERENCES guild_catalog_entries (guild_id, catalog_key, entry_key)
            ON UPDATE CASCADE ON DELETE CASCADE
    )
    """,
)


@dataclass(frozen=True, slots=True)
class _LegacyCatalog:
    """Freeze historical storage names independently of future runtime defaults."""

    table: str
    key_column: str
    prefix_column: str
    default_prefix: str
    has_variants: bool


_SOURCES = (
    _LegacyCatalog(
        "guild_member_interests",
        "interest_key",
        "member_interest_prefix",
        "interest-",
        False,
    ),
    _LegacyCatalog(
        "guild_adult_accesses",
        "access_key",
        "adult_access_prefix",
        "access-",
        True,
    ),
)


async def _fetchall(
    connection: aiosqlite.Connection,
    sql: str,
    parameters: tuple = (),
) -> list[aiosqlite.Row]:
    """Read named rows without changing the caller's connection row factory."""

    async with connection.execute(sql, parameters) as cursor:
        cursor.row_factory = aiosqlite.Row
        return await cursor.fetchall()


async def _has_rows(connection: aiosqlite.Connection, table: str) -> bool:
    """Probe a trusted historical table without loading its contents."""

    # table is chosen exclusively from the migration's fixed _SOURCES tuple.
    async with connection.execute(f"SELECT EXISTS(SELECT 1 FROM {table})") as cursor:
        return bool((await cursor.fetchone())[0])


async def _resolve_catalog(
    connection: aiosqlite.Connection,
    source: _LegacyCatalog,
    guild_id: int,
) -> str:
    """Reuse the exact configured prefix or create a migration-only definition.

    The V5 production schema has no declarative catalog rows yet. In that case
    we persist a catalog, but never synthesize an executable workflow or command.
    Existing definitions and workflow bindings are preserved unchanged.
    """

    settings = await _fetchall(
        connection,
        f"SELECT {source.prefix_column} AS prefix FROM guild_settings WHERE guild_id = ?",
        (guild_id,),
    )
    prefix = settings[0]["prefix"] if settings else None
    prefix = source.default_prefix if prefix is None else prefix
    if not prefix or prefix != prefix.strip():
        raise LegacyCatalogMigrationError(
            f"Guild {guild_id}: invalid historical prefix in {source.prefix_column}."
        )

    catalogs = await _fetchall(
        connection,
        "SELECT catalog_key, role_prefix FROM guild_catalogs WHERE guild_id = ?",
        (guild_id,),
    )
    exact = [row for row in catalogs if row["role_prefix"] == prefix]
    # An overlapping prefix would give the same roles two different domains.
    overlaps = [
        row
        for row in catalogs
        if row["role_prefix"] != prefix
        and (
            prefix.startswith(row["role_prefix"])
            or row["role_prefix"].startswith(prefix)
        )
    ]
    if overlaps or len(exact) > 1:
        raise LegacyCatalogMigrationError(
            f"Guild {guild_id}: ambiguous catalog prefix {prefix!r}."
        )
    if exact:
        return str(exact[0]["catalog_key"])

    catalog_key = f"migrated-{prefix.rstrip('-')}"
    if any(row["catalog_key"] == catalog_key for row in catalogs):
        raise LegacyCatalogMigrationError(
            f"Guild {guild_id}: catalog key {catalog_key!r} already has another prefix."
        )
    await connection.execute(
        """
        INSERT INTO guild_catalogs
            (guild_id, catalog_key, role_prefix, display_name, entry_name)
        VALUES (?, ?, ?, ?, ?)
        """,
        (guild_id, catalog_key, prefix, prefix.rstrip("-"), "Choix"),
    )
    return catalog_key


def _classify_rows(
    source: _LegacyCatalog,
    rows: list[aiosqlite.Row],
    guild_id: int,
) -> list[tuple[str, list[tuple[aiosqlite.Row, str]]]]:
    """Group historical variants; ordinary keys remain literal singletons."""

    by_key: dict[str, aiosqlite.Row] = {}
    for row in rows:
        key = row[source.key_column]
        if not key or key != key.strip() or key in by_key:
            raise LegacyCatalogMigrationError(
                f"Guild {guild_id}: invalid or duplicate key {key!r} in {source.table}."
            )
        by_key[key] = row

    if not source.has_variants:
        return [(key, [(row, "base")]) for key, row in sorted(by_key.items())]

    classification = CatalogVariantClassifier().classify(by_key)
    if classification.invalid_keys or classification.duplicate_keys:
        raise LegacyCatalogMigrationError(
            f"Guild {guild_id}: invalid historical access variants."
        )

    groups: list[tuple[str, list[tuple[aiosqlite.Row, str]]]] = []
    for pair in classification.pairs:
        # The no-AI row is deliberately first: its metadata always wins,
        # including None/empty values. No fallback to an AI robot emoji.
        groups.append(
            (
                pair.theme_key,
                [
                    (by_key[pair.no_ai_key], "no_ai"),
                    (by_key[pair.ai_key], "ai"),
                ],
            )
        )
    for keys, variant, prefix in (
        (classification.solo_keys, "base", ""),
        (classification.no_ai_only_keys, "no_ai", "no-ia-"),
        (classification.ai_only_keys, "ai", "ia-"),
    ):
        for key in keys:
            groups.append((key.removeprefix(prefix), [(by_key[key], variant)]))

    names = [key for key, _ in groups]
    if len(names) != len(set(names)):
        raise LegacyCatalogMigrationError(
            f"Guild {guild_id}: a singleton collides with a variant entry."
        )
    return groups


async def _copy_legacy_catalog(
    connection: aiosqlite.Connection,
    source: _LegacyCatalog,
) -> set[int]:
    """Transfer one nonempty source and prove every role and state was preserved."""

    rows = await _fetchall(connection, f"SELECT * FROM {source.table}")
    by_guild: dict[int, list[aiosqlite.Row]] = defaultdict(list)
    for row in rows:
        by_guild[row["guild_id"]].append(row)
    ai_guilds: set[int] = set()
    for guild_id, guild_rows in by_guild.items():
        catalog_key = await _resolve_catalog(connection, source, guild_id)
        for entry_key, targets in _classify_rows(source, guild_rows, guild_id):
            canonical = targets[0][0]
            await connection.execute(
                """
                INSERT INTO guild_catalog_entries
                    (guild_id, catalog_key, entry_key, label, description, emoji,
                     sort_order, enabled)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    guild_id,
                    catalog_key,
                    entry_key,
                    canonical["label"],
                    canonical["description"],
                    canonical["emoji"],
                    canonical["sort_order"],
                    canonical["enabled"],
                ),
            )
            for row, variant in targets:
                await connection.execute(
                    """
                    INSERT INTO guild_catalog_entry_targets
                        (guild_id, catalog_key, entry_key, role_id, role_name,
                         channel_id, channel_name, variant, enabled,
                         discord_present, role_manageable, channel_present,
                         mapping_valid, matches_policy)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        catalog_key,
                        entry_key,
                        row["role_id"],
                        row["role_name"],
                        row["channel_id"],
                        row["channel_name"],
                        variant,
                        row["enabled"],
                        row["discord_present"],
                        row["role_manageable"],
                        row["channel_present"],
                        row["mapping_valid"],
                        row["matches_policy"],
                    ),
                )
                if variant == "ai":
                    ai_guilds.add(guild_id)

    # A count alone cannot detect a substituted role or accidentally reset flag.
    # Compare the actual source identities, mappings and availability states.
    columns = (
        "guild_id",
        "role_id",
        "role_name",
        "channel_id",
        "channel_name",
        "enabled",
        "discord_present",
        "role_manageable",
        "channel_present",
        "mapping_valid",
        "matches_policy",
    )
    expected = {tuple(row[column] for column in columns) for row in rows}
    actual_rows = await _fetchall(
        connection,
        f"""
        SELECT {", ".join("t." + column for column in columns)}
        FROM guild_catalog_entry_targets AS t
        JOIN {source.table} AS s ON s.guild_id = t.guild_id AND s.role_id = t.role_id
        """,
    )
    actual = {tuple(row[column] for column in columns) for row in actual_rows}
    if len(actual_rows) != len(rows) or actual != expected:
        raise LegacyCatalogMigrationError(
            f"Target conservation failed for {source.table}."
        )
    return ai_guilds


async def _copy_ai_settings(
    connection: aiosqlite.Connection,
    ai_guilds: set[int],
) -> None:
    """Import a recorded AI identity, never infer a role ID from its name.

    Legacy AI targets prove a historical AI capability, but do not identify the
    preference role. Such guilds become enabled with a missing role to configure.
    A guild with no historical AI evidence stays unconfigured (NULL).
    """

    contexts = await _fetchall(
        connection,
        """
        SELECT guild_id, role_id, enabled FROM guild_context_definitions
        WHERE capability_key = 'ai_preference'
        """,
    )
    settings = {guild_id: (1, None) for guild_id in ai_guilds}
    for row in contexts:
        conflicts = await _fetchall(
            connection,
            "SELECT 1 FROM guild_catalog_entry_targets WHERE guild_id = ? AND role_id = ?",
            (row["guild_id"], row["role_id"]),
        )
        if conflicts:
            raise LegacyCatalogMigrationError(
                f"Guild {row['guild_id']}: AI preference role also appears in a catalog."
            )
        settings[row["guild_id"]] = (row["enabled"], row["role_id"])
    for guild_id, (enabled, role_id) in settings.items():
        await connection.execute(
            """
            INSERT INTO guild_settings (guild_id, ai_enabled, ai_role_id)
            VALUES (?, ?, ?)
            ON CONFLICT (guild_id) DO UPDATE SET
                ai_enabled = excluded.ai_enabled, ai_role_id = excluded.ai_role_id
            """,
            (guild_id, enabled, role_id),
        )


async def migrate_v11_data(
    connection: aiosqlite.Connection,
    *,
    transfer_legacy_data: bool,
) -> None:
    """Validate and retire legacy catalogs inside the caller's V11 transaction.

    Fresh initialization skips all legacy data reads. Existing databases probe
    each source with EXISTS and invoke conversion only for nonempty tables.
    AI contexts remain temporarily readable for the next config-server tranche;
    this storage-only tranche does not claim to switch existing UI writers.
    """

    if not connection.in_transaction:
        raise RuntimeError("V11 data migration requires an active transaction.")

    if transfer_legacy_data:
        ai_guilds: set[int] = set()
        for source in _SOURCES:
            if await _has_rows(connection, source.table):
                ai_guilds.update(await _copy_legacy_catalog(connection, source))
        async with connection.execute(
            "SELECT EXISTS(SELECT 1 FROM guild_context_definitions "
            "WHERE capability_key = 'ai_preference')"
        ) as cursor:
            has_ai_context = bool((await cursor.fetchone())[0])
        if ai_guilds or has_ai_context:
            await _copy_ai_settings(connection, ai_guilds)

    violations = await _fetchall(connection, "PRAGMA foreign_key_check")
    if violations:
        raise LegacyCatalogMigrationError(
            "Foreign key validation failed before source removal."
        )

    # Source destruction is last. Any subsequent failure also rolls it back.
    for source in _SOURCES:
        await connection.execute(f"DROP TABLE {source.table}")
