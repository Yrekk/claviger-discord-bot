from collections.abc import Sequence

import aiosqlite

from claviger.database.connection import DatabaseConnection


CURRENT_SCHEMA_VERSION = 2


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when the database schema is newer than this Claviger version."""


MIGRATIONS: dict[int, Sequence[str]] = {
    1: (),
    2: (
        """
        CREATE TABLE guild_settings (
            guild_id INTEGER PRIMARY KEY,
            member_role_name TEXT,
            adult_role_name TEXT,
            access_role_prefix TEXT,
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
        """,
    ),
}


class DatabaseSchema:
    """Initialize and migrate Claviger's SQLite schema."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get_version(self) -> int:
        """Return the current SQLite application schema version."""

        async with self.database.connect() as connection:
            cursor = await connection.execute(
                "PRAGMA user_version"
            )

            row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])

    async def initialize(self) -> None:
        """Initialize or migrate the database to the current schema version."""

        async with self.database.connect() as connection:
            current_version = await self._get_version(
                connection,
            )

            if current_version > CURRENT_SCHEMA_VERSION:
                raise UnsupportedSchemaVersionError(
                    "Database schema version "
                    f"{current_version} is newer than supported version "
                    f"{CURRENT_SCHEMA_VERSION}."
                )

            for version in range(
                current_version + 1,
                CURRENT_SCHEMA_VERSION + 1,
            ):
                await self._apply_migration(
                    connection,
                    version,
                )

    async def _get_version(
        self,
        connection: aiosqlite.Connection,
    ) -> int:
        """Return the schema version using an existing connection."""

        cursor = await connection.execute(
            "PRAGMA user_version"
        )

        row = await cursor.fetchone()

        if row is None:
            return 0

        return int(row[0])

    async def _apply_migration(
        self,
        connection: aiosqlite.Connection,
        version: int,
    ) -> None:
        """Apply one schema migration atomically."""

        statements = MIGRATIONS.get(version)

        if statements is None:
            raise RuntimeError(
                f"Missing database migration for schema version {version}."
            )

        try:
            await connection.execute(
                "BEGIN IMMEDIATE"
            )

            for statement in statements:
                await connection.execute(
                    statement
                )

            await connection.execute(
                f"PRAGMA user_version = {version}"
            )

            await connection.commit()

        except (aiosqlite.Error, RuntimeError):
            await connection.rollback()
            raise