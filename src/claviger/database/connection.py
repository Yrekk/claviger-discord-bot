from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


class DatabaseUnavailableError(RuntimeError):
    """Raised when Claviger cannot access its SQLite database."""


class DatabaseConnection:
    """Manage SQLite connections used by Claviger."""

    def __init__(
        self,
        database_path: str | Path,
    ) -> None:
        self.database_path = Path(database_path)

    @asynccontextmanager
    async def connect(
        self,
    ) -> AsyncGenerator[aiosqlite.Connection]:
        """Open a SQLite connection and close it automatically."""

        try:
            connection = await aiosqlite.connect(
                self.database_path,
            )
        except (aiosqlite.Error, OSError) as error:
            raise DatabaseUnavailableError(
                f"Unable to open SQLite database: {self.database_path}"
            ) from error

        try:
            await connection.execute("PRAGMA foreign_keys = ON")

            yield connection
        finally:
            await connection.close()

    async def is_available(self) -> bool:
        """Return whether the existing SQLite database can currently be reached."""

        if not self.exists():
            return False

        try:
            async with self.connect() as connection:
                await connection.execute("SELECT 1")
        except (DatabaseUnavailableError, aiosqlite.Error):
            return False

        return True

    async def check_integrity(self) -> bool:
        """Return whether SQLite quick_check reports a coherent database."""

        if not self.exists():
            return False

        async with self.connect() as connection:
            cursor = await connection.execute("PRAGMA quick_check")
            rows = await cursor.fetchall()

        return len(rows) == 1 and str(rows[0][0]).casefold() == "ok"

    def exists(self) -> bool:
        """Return whether the configured SQLite database file exists."""
        return self.database_path.is_file()


class DatabaseMissingError(DatabaseUnavailableError):
    """Raised when Claviger's SQLite database does not exist."""
