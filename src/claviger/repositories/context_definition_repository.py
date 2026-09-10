from typing import cast

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.context_definition_model import (
    ContextDefinition,
    ContextValueType,
)


class ContextDefinitionRepository:
    """Read declarative guild context definitions from SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        *,
        guild_id: int,
        context_key: str,
    ) -> ContextDefinition | None:
        """Return one context definition, or None when it does not exist."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        context_key,
                        capability_key,
                        value_type,
                        role_id,
                        label,
                        description,
                        sort_order,
                        enabled
                    FROM guild_context_definitions
                    WHERE guild_id = ?
                      AND context_key = ?
                    """,
                    (
                        guild_id,
                        context_key,
                    ),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to read context definition "
                f"{context_key!r} for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return self._row_to_definition(
            row,
        )

    async def list_for_guild(
        self,
        guild_id: int,
    ) -> tuple[ContextDefinition, ...]:
        """Return every context definition configured for one guild."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        context_key,
                        capability_key,
                        value_type,
                        role_id,
                        label,
                        description,
                        sort_order,
                        enabled
                    FROM guild_context_definitions
                    WHERE guild_id = ?
                    ORDER BY
                        sort_order,
                        context_key
                    """,
                    (guild_id,),
                )

                rows = await cursor.fetchall()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read context definitions for guild {guild_id}."
            ) from error

        return tuple(self._row_to_definition(row) for row in rows)

    def _ensure_database_exists(
        self,
    ) -> None:
        """Reject reads that would implicitly create an empty SQLite file."""

        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )

    @staticmethod
    def _row_to_definition(
        row: aiosqlite.Row,
    ) -> ContextDefinition:
        """Convert one SQLite row into a context definition."""

        return ContextDefinition(
            guild_id=row["guild_id"],
            context_key=row["context_key"],
            capability_key=row["capability_key"],
            value_type=cast(
                ContextValueType,
                row["value_type"],
            ),
            role_id=row["role_id"],
            label=row["label"],
            description=row["description"],
            sort_order=row["sort_order"],
            enabled=bool(row["enabled"]),
        )
