import re
from typing import Generic, TypeVar

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.role_channel_catalog import RoleChannelCatalogEntry

CatalogEntryT = TypeVar(
    "CatalogEntryT",
    bound=RoleChannelCatalogEntry,
)

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class RoleChannelCatalogRepository(
    Generic[CatalogEntryT],
):
    """Persist a Discord role-to-channel catalog in SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
        *,
        table_name: str,
        key_column: str,
        entry_type: type[CatalogEntryT],
        entry_label: str,
        not_found_error: type[RuntimeError],
    ) -> None:
        self.database = database
        self.table_name = self._validate_identifier(
            table_name,
        )
        self.key_column = self._validate_identifier(
            key_column,
        )
        self.entry_type = entry_type
        self.entry_label = entry_label
        self.not_found_error = not_found_error

    async def list_for_guild(
        self,
        guild_id: int,
    ) -> list[CatalogEntryT]:
        """Return every known catalog entry for a guild."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    f"""
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        {self.key_column} AS catalog_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM {self.table_name}
                    WHERE guild_id = ?
                    ORDER BY
                        sort_order,
                        role_name,
                        role_id
                    """,
                    (guild_id,),
                )

                rows = await cursor.fetchall()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to read {self.entry_label} catalog for guild {guild_id}.")
            ) from error

        return [self._to_entry(row) for row in rows]

    async def get(
        self,
        guild_id: int,
        role_id: int,
    ) -> CatalogEntryT | None:
        """Return one entry by its stable Discord role identity."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    f"""
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        {self.key_column} AS catalog_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM {self.table_name}
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        guild_id,
                        role_id,
                    ),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to read {self.entry_label} {role_id} for guild {guild_id}.")
            ) from error

        if row is None:
            return None

        return self._to_entry(row)

    async def create_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        catalog_key: str,
        channel_id: int,
        channel_name: str,
        *,
        role_manageable: bool = True,
    ) -> CatalogEntryT:
        """Create a newly discovered Discord catalog entry."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    f"""
                    INSERT INTO {self.table_name} (
                        guild_id,
                        role_id,
                        role_name,
                        {self.key_column},
                        channel_id,
                        channel_name,
                        role_manageable
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        role_id,
                        role_name,
                        catalog_key,
                        channel_id,
                        channel_name,
                        role_manageable,
                    ),
                )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to create {self.entry_label} {role_id} for guild {guild_id}.")
            ) from error

        entry = await self.get(
            guild_id,
            role_id,
        )

        if entry is None:
            raise DatabaseUnavailableError(
                (
                    f"{self.entry_label.capitalize()} was created "
                    "but could not be reloaded for "
                    f"guild {guild_id}, role {role_id}."
                )
            )

        return entry

    async def refresh_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        catalog_key: str,
        channel_id: int,
        channel_name: str,
        *,
        role_manageable: bool = True,
    ) -> None:
        """Refresh Discord-owned data without changing human metadata."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET
                        role_name = ?,
                        {self.key_column} = ?,
                        channel_id = ?,
                        channel_name = ?,
                        discord_present = 1,
                        role_manageable = ?,
                        channel_present = 1,
                        mapping_valid = 1,
                        matches_policy = 1
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        role_name,
                        catalog_key,
                        channel_id,
                        channel_name,
                        role_manageable,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise self.not_found_error(
                        (
                            f"{self.entry_label.capitalize()} "
                            "does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except self.not_found_error:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    f"Unable to refresh {self.entry_label} "
                    f"{role_id} for guild {guild_id}."
                )
            ) from error

    async def update_sync_state(
        self,
        guild_id: int,
        role_id: int,
        *,
        discord_present: bool,
        role_manageable: bool,
        channel_present: bool,
        mapping_valid: bool,
        matches_policy: bool,
    ) -> None:
        """Update synchronization state without erasing stored identities."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET
                        discord_present = ?,
                        role_manageable = ?,
                        channel_present = ?,
                        mapping_valid = ?,
                        matches_policy = ?
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise self.not_found_error(
                        (
                            f"{self.entry_label.capitalize()} "
                            "does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except self.not_found_error:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    "Unable to update synchronization state for "
                    f"{self.entry_label} {role_id} "
                    f"in guild {guild_id}."
                )
            ) from error

    async def get_next_incomplete(
        self,
        guild_id: int,
    ) -> CatalogEntryT | None:
        """Return the next usable entry missing required metadata."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    f"""
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        {self.key_column} AS catalog_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM {self.table_name}
                    WHERE guild_id = ?
                      AND enabled = 1
                      AND discord_present = 1
                      AND role_manageable = 1
                      AND channel_present = 1
                      AND mapping_valid = 1
                      AND matches_policy = 1
                      AND (
                          label IS NULL
                          OR description IS NULL
                      )
                    ORDER BY
                        sort_order,
                        role_name,
                        role_id
                    LIMIT 1
                    """,
                    (guild_id,),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    f"Unable to find incomplete "
                    f"{self.entry_label} entries "
                    f"for guild {guild_id}."
                )
            ) from error

        if row is None:
            return None

        return self._to_entry(row)

    async def update_metadata(
        self,
        guild_id: int,
        role_id: int,
        *,
        label: str,
        description: str,
        emoji: str | None,
    ) -> None:
        """Update human-managed metadata for one catalog entry."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET
                        label = ?,
                        description = ?,
                        emoji = ?
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        label,
                        description,
                        emoji,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise self.not_found_error(
                        (
                            f"{self.entry_label.capitalize()} "
                            "does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except self.not_found_error:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    f"Unable to update metadata for "
                    f"{self.entry_label} {role_id} "
                    f"in guild {guild_id}."
                )
            ) from error

    def _ensure_database_exists(self) -> None:
        """Reject access without implicitly creating SQLite."""

        if not self.database.exists():
            raise DatabaseMissingError(
                (f"SQLite database does not exist: {self.database.database_path}")
            )

    def _to_entry(
        self,
        row: aiosqlite.Row,
    ) -> CatalogEntryT:
        """Convert one SQLite row into the configured domain model."""

        return self.entry_type(
            guild_id=row["guild_id"],
            role_id=row["role_id"],
            role_name=row["role_name"],
            catalog_key=row["catalog_key"],
            channel_id=row["channel_id"],
            channel_name=row["channel_name"],
            label=row["label"],
            description=row["description"],
            emoji=row["emoji"],
            sort_order=row["sort_order"],
            enabled=bool(row["enabled"]),
            discord_present=bool(row["discord_present"]),
            role_manageable=bool(row["role_manageable"]),
            channel_present=bool(row["channel_present"]),
            mapping_valid=bool(row["mapping_valid"]),
            matches_policy=bool(row["matches_policy"]),
        )

    @staticmethod
    def _validate_identifier(
        identifier: str,
    ) -> str:
        """Accept only simple internal SQLite identifiers."""

        if _IDENTIFIER_PATTERN.fullmatch(identifier) is None:
            raise ValueError(f"Invalid SQLite identifier: {identifier}")

        return identifier
