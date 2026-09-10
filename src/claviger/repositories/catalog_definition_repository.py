import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.catalog_definition_model import CatalogDefinition


class CatalogDefinitionRepository:
    """Read declarative guild catalog definitions from SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        *,
        guild_id: int,
        catalog_key: str,
    ) -> CatalogDefinition | None:
        """Return one catalog definition, or None when it does not exist."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        catalog_key,
                        role_prefix,
                        display_name,
                        entry_name,
                        description,
                        sort_order,
                        enabled
                    FROM guild_catalogs
                    WHERE guild_id = ?
                      AND catalog_key = ?
                    """,
                    (
                        guild_id,
                        catalog_key,
                    ),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to read catalog definition "
                f"{catalog_key!r} for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return self._row_to_definition(
            row,
        )

    async def list_for_guild(
        self,
        guild_id: int,
    ) -> tuple[CatalogDefinition, ...]:
        """Return every catalog definition configured for one guild."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        catalog_key,
                        role_prefix,
                        display_name,
                        entry_name,
                        description,
                        sort_order,
                        enabled
                    FROM guild_catalogs
                    WHERE guild_id = ?
                    ORDER BY
                        sort_order,
                        catalog_key
                    """,
                    (guild_id,),
                )

                rows = await cursor.fetchall()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read catalog definitions for guild {guild_id}."
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
    ) -> CatalogDefinition:
        """Convert one SQLite row into a catalog definition."""

        return CatalogDefinition(
            guild_id=row["guild_id"],
            catalog_key=row["catalog_key"],
            role_prefix=row["role_prefix"],
            display_name=row["display_name"],
            entry_name=row["entry_name"],
            description=row["description"],
            sort_order=row["sort_order"],
            enabled=bool(row["enabled"]),
        )
