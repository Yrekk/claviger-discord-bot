import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)


class DatabaseOwnershipRepository:
    """Persist the Discord application that owns one Claviger database."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get_application_id(
        self,
    ) -> int | None:
        """Return the owning Discord application ID, if one is bound."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    SELECT application_id
                    FROM database_ownership
                    WHERE singleton_id = 1
                    """
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to read database application ownership."
            ) from error

        if row is None:
            return None

        return int(row[0])

    async def bind(
        self,
        application_id: int,
    ) -> None:
        """Bind an unowned database to one Discord application."""

        if application_id <= 0:
            raise ValueError("Discord application ID must be greater than zero.")

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    """
                    INSERT INTO database_ownership (
                        singleton_id,
                        application_id
                    )
                    VALUES (1, ?)
                    """,
                    (application_id,),
                )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to bind database application ownership."
            ) from error

    def _ensure_database_exists(
        self,
    ) -> None:
        """Reject access that would implicitly create an SQLite database."""

        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
