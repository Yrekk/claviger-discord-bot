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

    async def sync_discovered_catalog(
        self,
        *,
        guild_id: int,
        catalog_key: str,
        entries: tuple[CatalogEntry, ...],
    ) -> None:
        """Refresh one catalog from a conservative live Discord discovery."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        normalized_key = catalog_key.strip()

        if not normalized_key:
            raise ValueError("Catalog key cannot be empty.")

        discovered_role_ids = tuple(
            target.role_id
            for entry in entries
            for target in entry.targets
        )

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute("BEGIN IMMEDIATE")

                if discovered_role_ids:
                    placeholders = ", ".join(
                        "?"
                        for _ in discovered_role_ids
                    )
                    await connection.execute(
                        f"""
                        UPDATE guild_catalog_entry_targets
                        SET
                            discord_present = 0,
                            role_manageable = 0,
                            channel_present = 0,
                            mapping_valid = 0
                        WHERE guild_id = ?
                          AND catalog_key = ?
                          AND role_id NOT IN ({placeholders})
                        """,
                        (
                            guild_id,
                            normalized_key,
                            *discovered_role_ids,
                        ),
                    )
                else:
                    await connection.execute(
                        """
                        UPDATE guild_catalog_entry_targets
                        SET
                            discord_present = 0,
                            role_manageable = 0,
                            channel_present = 0,
                            mapping_valid = 0
                        WHERE guild_id = ?
                          AND catalog_key = ?
                        """,
                        (
                            guild_id,
                            normalized_key,
                        ),
                    )

                for entry in entries:
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
                        ON CONFLICT (
                            guild_id,
                            catalog_key,
                            entry_key
                        )
                        DO NOTHING
                        """,
                        (
                            guild_id,
                            normalized_key,
                            entry.entry_key,
                            entry.label,
                            entry.description,
                            entry.emoji,
                            entry.sort_order,
                            entry.enabled,
                        ),
                    )

                    for target in entry.targets:
                        await connection.execute(
                            """
                            DELETE FROM guild_catalog_entry_targets
                            WHERE guild_id = ?
                              AND catalog_key = ?
                              AND entry_key = ?
                              AND variant = ?
                              AND role_id <> ?
                            """,
                            (
                                guild_id,
                                normalized_key,
                                entry.entry_key,
                                target.variant,
                                target.role_id,
                            ),
                        )

                        await connection.execute(
                            """
                            INSERT INTO guild_catalog_entry_targets (
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
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT (
                                guild_id,
                                role_id
                            )
                            DO UPDATE SET
                                catalog_key = excluded.catalog_key,
                                entry_key = excluded.entry_key,
                                role_name = excluded.role_name,
                                channel_id = excluded.channel_id,
                                channel_name = excluded.channel_name,
                                variant = excluded.variant,
                                discord_present = excluded.discord_present,
                                role_manageable = excluded.role_manageable,
                                channel_present = excluded.channel_present,
                                mapping_valid = excluded.mapping_valid,
                                matches_policy = excluded.matches_policy
                            """,
                            (
                                guild_id,
                                normalized_key,
                                entry.entry_key,
                                target.role_id,
                                target.role_name,
                                target.channel_id,
                                target.channel_name,
                                target.variant,
                                target.enabled,
                                target.discord_present,
                                target.role_manageable,
                                target.channel_present,
                                target.mapping_valid,
                                target.matches_policy,
                            ),
                        )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to synchronize catalog {normalized_key!r} "
                f"for guild {guild_id}."
            ) from error

    def _ensure_database_exists(
        self,
    ) -> None:
        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
