from collections import defaultdict
from collections.abc import Sequence
from typing import cast

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
    CatalogTargetVariant,
)


class CatalogEntryRepository:
    """Read V11 logical catalog entries and their Discord role targets."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def list_for_catalog(
        self,
        *,
        guild_id: int,
        catalog_key: str,
    ) -> tuple[CatalogEntry, ...]:
        """Return all logical entries for one guild catalog in stable order."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        normalized_key = catalog_key.strip()

        if not normalized_key:
            raise ValueError("Catalog key cannot be empty.")

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                entry_cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        catalog_key,
                        entry_key,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled
                    FROM guild_catalog_entries
                    WHERE guild_id = ?
                      AND catalog_key = ?
                    ORDER BY
                        sort_order,
                        entry_key
                    """,
                    (
                        guild_id,
                        normalized_key,
                    ),
                )
                entry_rows: Sequence[aiosqlite.Row] = await entry_cursor.fetchall()

                target_cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        catalog_key,
                        entry_key,
                        role_id,
                        role_name,
                        channel_id,
                        channel_name,
                        variant,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM guild_catalog_entry_targets
                    WHERE guild_id = ?
                      AND catalog_key = ?
                    ORDER BY
                        entry_key,
                        CASE variant
                            WHEN 'base' THEN 0
                            WHEN 'no_ai' THEN 1
                            WHEN 'ai' THEN 2
                            ELSE 99
                        END,
                        role_id
                    """,
                    (
                        guild_id,
                        normalized_key,
                    ),
                )
                target_rows: Sequence[aiosqlite.Row] = await target_cursor.fetchall()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read catalog {normalized_key!r} for guild {guild_id}."
            ) from error

        targets_by_entry: dict[str, list[CatalogEntryTarget]] = defaultdict(list)

        for row in target_rows:
            targets_by_entry[str(row["entry_key"])].append(
                CatalogEntryTarget(
                    guild_id=int(row["guild_id"]),
                    catalog_key=str(row["catalog_key"]),
                    entry_key=str(row["entry_key"]),
                    role_id=int(row["role_id"]),
                    role_name=str(row["role_name"]),
                    channel_id=int(row["channel_id"]),
                    channel_name=str(row["channel_name"]),
                    variant=cast(
                        CatalogTargetVariant,
                        str(row["variant"]),
                    ),
                    enabled=bool(row["enabled"]),
                    discord_present=bool(row["discord_present"]),
                    role_manageable=bool(row["role_manageable"]),
                    channel_present=bool(row["channel_present"]),
                    mapping_valid=bool(row["mapping_valid"]),
                    matches_policy=bool(row["matches_policy"]),
                )
            )

        return tuple(
            CatalogEntry(
                guild_id=int(row["guild_id"]),
                catalog_key=str(row["catalog_key"]),
                entry_key=str(row["entry_key"]),
                label=row["label"],
                description=row["description"],
                emoji=row["emoji"],
                sort_order=int(row["sort_order"]),
                enabled=bool(row["enabled"]),
                targets=tuple(
                    targets_by_entry.get(
                        str(row["entry_key"]),
                        (),
                    )
                ),
            )
            for row in entry_rows
        )

    def _ensure_database_exists(
        self,
    ) -> None:
        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
