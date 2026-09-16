"""Transform specialized V10 guild data into the generic V11 model."""

from dataclasses import dataclass
from itertools import groupby
from collections.abc import Iterable

import aiosqlite

from claviger.services.catalogs.catalog_variant_classifier import (
    CatalogVariantClassifier,
)

AI_CAPABILITY_KEY = "ai_preference"


class MigrationV11DataError(RuntimeError):
    """Raised when V10 data cannot be migrated without ambiguity or loss."""


@dataclass(frozen=True, slots=True)
class _LegacyCatalogRow:
    """Represent one historical questionnaire row during V11 migration."""

    guild_id: int
    role_id: int
    source_key: str
    label: str | None
    description: str | None
    emoji: str | None
    sort_order: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class _LegacyCatalogFamily:
    """Describe one historical catalog family understood only by migration."""

    table_name: str
    key_column: str
    prefix_column: str
    default_prefix: str
    catalog_key: str
    display_name: str
    entry_name: str


LEGACY_CATALOG_FAMILIES = (
    _LegacyCatalogFamily(
        table_name="guild_member_interests",
        key_column="interest_key",
        prefix_column="member_interest_prefix",
        default_prefix="interest-",
        catalog_key="legacy-interests",
        display_name="Intérêts migrés",
        entry_name="intérêt",
    ),
    _LegacyCatalogFamily(
        table_name="guild_adult_accesses",
        key_column="access_key",
        prefix_column="adult_access_prefix",
        default_prefix="access-",
        catalog_key="legacy-accesses",
        display_name="Accès migrés",
        entry_name="accès",
    ),
)


async def migrate_v11(
    connection: aiosqlite.Connection,
) -> None:
    """Convert V10 specialized guild data to V11 inside the caller transaction."""

    source_row_count = await _count_legacy_catalog_rows(
        connection,
    )

    for family in LEGACY_CATALOG_FAMILIES:
        await _migrate_legacy_catalog_family(
            connection,
            family=family,
        )

    target_row_count = await _count_catalog_targets(
        connection,
    )

    if target_row_count != source_row_count:
        raise MigrationV11DataError(
            "V11 catalog migration did not preserve every legacy role target: "
            f"expected {source_row_count}, migrated {target_row_count}."
        )

    await _migrate_guild_settings(
        connection,
    )

    # Destructive cleanup is deliberately last. Every old catalog row has a
    # persisted target and guild-wide AI state has already been transferred.
    await connection.execute(
        "DROP TABLE guild_member_interests"
    )
    await connection.execute(
        "DROP TABLE guild_adult_accesses"
    )


async def _count_legacy_catalog_rows(
    connection: aiosqlite.Connection,
) -> int:
    """Return the number of specialized rows that must become generic targets."""

    total = 0

    for family in LEGACY_CATALOG_FAMILIES:
        cursor = await connection.execute(
            f"SELECT COUNT(*) FROM {family.table_name}"
        )
        row = await cursor.fetchone()
        total += int(row[0])

    return total


async def _count_catalog_targets(
    connection: aiosqlite.Connection,
) -> int:
    """Return the number of generic targets created by this migration."""

    cursor = await connection.execute(
        "SELECT COUNT(*) FROM guild_catalog_entry_targets"
    )
    row = await cursor.fetchone()
    return int(row[0])


async def _migrate_legacy_catalog_family(
    connection: aiosqlite.Connection,
    *,
    family: _LegacyCatalogFamily,
) -> None:
    """Move one historical family into logical entries and explicit targets."""

    cursor = await connection.execute(
        f"""
        SELECT
            guild_id,
            role_id,
            {family.key_column},
            label,
            description,
            emoji,
            sort_order,
            enabled
        FROM {family.table_name}
        ORDER BY
            guild_id,
            sort_order,
            role_id
        """
    )

    rows = await cursor.fetchall()

    for guild_id, guild_rows_iterator in groupby(
        rows,
        key=lambda row: int(row[0]),
    ):
        guild_rows = tuple(
            guild_rows_iterator,
        )

        role_prefix = await _resolve_legacy_role_prefix(
            connection,
            guild_id=guild_id,
            family=family,
        )

        catalog_key = await _resolve_or_create_catalog(
            connection,
            guild_id=guild_id,
            role_prefix=role_prefix,
            family=family,
        )

        normalized_rows = tuple(
            _build_legacy_catalog_row(
                row,
                role_prefix=role_prefix,
            )
            for row in guild_rows
        )

        await _migrate_normalized_rows(
            connection,
            catalog_key=catalog_key,
            rows=normalized_rows,
        )


def _build_legacy_catalog_row(
    row: tuple,
    *,
    role_prefix: str,
) -> _LegacyCatalogRow:
    """Normalize one old row without deriving meaning from the Discord role name."""

    guild_id = int(
        row[0],
    )
    role_id = int(
        row[1],
    )

    if guild_id <= 0:
        raise MigrationV11DataError(
            f"Legacy catalog row contains invalid guild ID {guild_id}."
        )

    if role_id <= 0:
        raise MigrationV11DataError(
            f"Legacy catalog row contains invalid role ID {role_id}."
        )

    source_key = str(
        row[2],
    ).strip()

    # Historical databases normally store `ia-test` rather than the full role
    # name `access-ia-test`. Accept the prefixed form too so the migration is
    # robust to older manually populated DEV databases.
    if role_prefix and source_key.startswith(
        role_prefix,
    ):
        source_key = source_key.removeprefix(
            role_prefix,
        )

    return _LegacyCatalogRow(
        guild_id=guild_id,
        role_id=role_id,
        source_key=source_key,
        label=_optional_text(
            row[3],
        ),
        description=_optional_text(
            row[4],
        ),
        emoji=_optional_text(
            row[5],
        ),
        sort_order=int(
            row[6],
        ),
        enabled=bool(
            row[7],
        ),
    )


async def _resolve_legacy_role_prefix(
    connection: aiosqlite.Connection,
    *,
    guild_id: int,
    family: _LegacyCatalogFamily,
) -> str:
    """Return the old configured role prefix for one guild and catalog family."""

    cursor = await connection.execute(
        f"""
        SELECT {family.prefix_column}
        FROM guild_settings
        WHERE guild_id = ?
        """,
        (
            guild_id,
        ),
    )

    row = await cursor.fetchone()

    if row is None:
        return family.default_prefix

    configured_prefix = _optional_text(
        row[0],
    )

    return configured_prefix or family.default_prefix


async def _resolve_or_create_catalog(
    connection: aiosqlite.Connection,
    *,
    guild_id: int,
    role_prefix: str,
    family: _LegacyCatalogFamily,
) -> str:
    """Reuse a catalog owning the old prefix, or create a migration-owned one."""

    cursor = await connection.execute(
        """
        SELECT catalog_key
        FROM guild_catalogs
        WHERE guild_id = ?
          AND role_prefix = ?
        """,
        (
            guild_id,
            role_prefix,
        ),
    )

    row = await cursor.fetchone()

    if row is not None:
        return str(
            row[0],
        )

    catalog_key = await _next_available_catalog_key(
        connection,
        guild_id=guild_id,
        base_key=family.catalog_key,
    )

    await connection.execute(
        """
        INSERT INTO guild_catalogs (
            guild_id,
            catalog_key,
            role_prefix,
            display_name,
            entry_name,
            description,
            sort_order,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            catalog_key,
            role_prefix,
            family.display_name,
            family.entry_name,
            "Catalogue créé automatiquement lors de la migration V11.",
            0,
            1,
        ),
    )

    return catalog_key


async def _next_available_catalog_key(
    connection: aiosqlite.Connection,
    *,
    guild_id: int,
    base_key: str,
) -> str:
    """Return a deterministic catalog key without overwriting existing data."""

    candidate = base_key
    suffix = 2

    while True:
        cursor = await connection.execute(
            """
            SELECT 1
            FROM guild_catalogs
            WHERE guild_id = ?
              AND catalog_key = ?
            """,
            (
                guild_id,
                candidate,
            ),
        )

        if await cursor.fetchone() is None:
            return candidate

        candidate = f"{base_key}-{suffix}"
        suffix += 1


async def _migrate_normalized_rows(
    connection: aiosqlite.Connection,
    *,
    catalog_key: str,
    rows: tuple[_LegacyCatalogRow, ...],
) -> None:
    """Deduplicate questionnaire choices while preserving every role target."""

    classifier = CatalogVariantClassifier()

    classification = classifier.classify(
        row.source_key
        for row in rows
    )

    if classification.invalid_keys:
        raise MigrationV11DataError(
            "V11 cannot migrate invalid legacy catalog keys: "
            f"{classification.invalid_keys!r}."
        )

    mapping: dict[str, tuple[str, str]] = {}

    for pair in classification.pairs:
        mapping[pair.no_ai_key] = (
            pair.theme_key,
            "no_ai",
        )
        mapping[pair.ai_key] = (
            pair.theme_key,
            "ai",
        )

    for source_key in classification.solo_keys:
        mapping[source_key] = (
            source_key,
            "default",
        )

    for source_key in classification.ai_only_keys:
        mapping[source_key] = (
            source_key.removeprefix(
                classifier.AI_PREFIX,
            ),
            "ai",
        )

    for source_key in classification.no_ai_only_keys:
        mapping[source_key] = (
            source_key.removeprefix(
                classifier.NO_AI_PREFIX,
            ),
            "no_ai",
        )

    grouped_rows: dict[str, list[tuple[_LegacyCatalogRow, str]]] = {}

    for row in rows:
        try:
            entry_key, variant = mapping[
                row.source_key
            ]
        except KeyError as error:
            raise MigrationV11DataError(
                "V11 could not classify legacy catalog key "
                f"{row.source_key!r}."
            ) from error

        grouped_rows.setdefault(
            entry_key,
            [],
        ).append(
            (
                row,
                variant,
            )
        )

    for entry_key, entry_rows in sorted(
        grouped_rows.items(),
    ):
        await _insert_catalog_entry(
            connection,
            catalog_key=catalog_key,
            entry_key=entry_key,
            rows=entry_rows,
        )


async def _insert_catalog_entry(
    connection: aiosqlite.Connection,
    *,
    catalog_key: str,
    entry_key: str,
    rows: list[tuple[_LegacyCatalogRow, str]],
) -> None:
    """Create one logical entry and all role targets represented by its old rows."""

    ordered_rows = sorted(
        rows,
        key=lambda item: (
            item[0].sort_order,
            item[0].role_id,
        ),
    )

    first_row = ordered_rows[0][0]

    await connection.execute(
        """
        INSERT INTO guild_catalog_entries (
            guild_id,
            catalog_key,
            entry_key,
            label,
            description,
            emoji,
            sort_order,
            enabled
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            first_row.guild_id,
            catalog_key,
            entry_key,
            _first_text(
                item[0].label
                for item in ordered_rows
            ),
            _first_text(
                item[0].description
                for item in ordered_rows
            ),
            _first_text(
                item[0].emoji
                for item in ordered_rows
            ),
            min(
                item[0].sort_order
                for item in ordered_rows
            ),
            int(
                any(
                    item[0].enabled
                    for item in ordered_rows
                )
            ),
        ),
    )

    for row, variant in ordered_rows:
        await connection.execute(
            """
            INSERT INTO guild_catalog_entry_targets (
                guild_id,
                catalog_key,
                entry_key,
                role_id,
                variant
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                row.guild_id,
                catalog_key,
                entry_key,
                row.role_id,
                variant,
            ),
        )


async def _migrate_guild_settings(
    connection: aiosqlite.Connection,
) -> None:
    """Replace specialized V10 settings with guild-wide AI configuration."""

    await connection.execute(
        """
        ALTER TABLE guild_settings
        RENAME TO guild_settings_v10_legacy
        """
    )

    await connection.execute(
        """
        CREATE TABLE guild_settings (
            guild_id INTEGER PRIMARY KEY
                CHECK (guild_id > 0),

            ai_enabled INTEGER NOT NULL DEFAULT 0
                CHECK (ai_enabled IN (0, 1)),

            ai_role_id INTEGER
                CHECK (ai_role_id IS NULL OR ai_role_id > 0)
        )
        """
    )

    cursor = await connection.execute(
        """
        SELECT guild_id
        FROM guild_settings_v10_legacy

        UNION

        SELECT guild_id
        FROM guild_context_definitions
        WHERE capability_key = ?

        ORDER BY guild_id
        """,
        (
            AI_CAPABILITY_KEY,
        ),
    )

    guild_ids = tuple(
        int(row[0])
        for row in await cursor.fetchall()
    )

    for guild_id in guild_ids:
        ai_role_id, ai_enabled = await _resolve_legacy_ai_state(
            connection,
            guild_id=guild_id,
        )

        await connection.execute(
            """
            INSERT INTO guild_settings (
                guild_id,
                ai_enabled,
                ai_role_id
            )
            VALUES (?, ?, ?)
            """,
            (
                guild_id,
                int(
                    ai_enabled,
                ),
                ai_role_id,
            ),
        )

    await _remove_legacy_ai_contexts(
        connection,
    )

    await connection.execute(
        "DROP TABLE guild_settings_v10_legacy"
    )


async def _resolve_legacy_ai_state(
    connection: aiosqlite.Connection,
    *,
    guild_id: int,
) -> tuple[int | None, bool]:
    """Map effective V10 AI-context usage into one guild-wide V11 setting."""

    cursor = await connection.execute(
        """
        SELECT
            context_key,
            role_id,
            enabled
        FROM guild_context_definitions
        WHERE guild_id = ?
          AND capability_key = ?
        """,
        (
            guild_id,
            AI_CAPABILITY_KEY,
        ),
    )

    definition = await cursor.fetchone()

    if definition is None:
        return None, False

    context_key = str(
        definition[0],
    )
    role_id = int(
        definition[1],
    )

    if role_id <= 0:
        raise MigrationV11DataError(
            f"Guild {guild_id} has invalid AI role ID {role_id}."
        )

    cursor = await connection.execute(
        """
        SELECT COUNT(*)
        FROM guild_workflow_contexts
        WHERE guild_id = ?
          AND context_key = ?
          AND enabled = 1
        """,
        (
            guild_id,
            context_key,
        ),
    )

    binding_count = int(
        (
            await cursor.fetchone()
        )[0]
    )

    ai_enabled = bool(
        definition[2]
    ) and binding_count > 0

    return role_id, ai_enabled


async def _remove_legacy_ai_contexts(
    connection: aiosqlite.Connection,
) -> None:
    """Remove only obsolete AI-preference contexts after settings migrate."""

    cursor = await connection.execute(
        """
        SELECT
            guild_id,
            context_key
        FROM guild_context_definitions
        WHERE capability_key = ?
        """,
        (
            AI_CAPABILITY_KEY,
        ),
    )

    contexts = await cursor.fetchall()

    for guild_id, context_key in contexts:
        await connection.execute(
            """
            DELETE FROM guild_workflow_contexts
            WHERE guild_id = ?
              AND context_key = ?
            """,
            (
                int(
                    guild_id,
                ),
                str(
                    context_key,
                ),
            ),
        )

    await connection.execute(
        """
        DELETE FROM guild_context_definitions
        WHERE capability_key = ?
        """,
        (
            AI_CAPABILITY_KEY,
        ),
    )


def _optional_text(
    value: object,
) -> str | None:
    """Normalize optional legacy text without inventing replacement metadata."""

    if value is None:
        return None

    text = str(
        value,
    ).strip()

    return text or None


def _first_text(
    values: Iterable[str | None],
) -> str | None:
    """Return the first non-empty metadata value in deterministic row order."""

    for value in values:
        if value:
            return value

    return None
