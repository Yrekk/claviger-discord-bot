import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


class DatabaseUnavailableError(RuntimeError):
    """Raised when Claviger cannot access its SQLite database."""


_INTEGRITY_ERROR_CODES = {
    sqlite3.SQLITE_CORRUPT,
    sqlite3.SQLITE_NOTADB,
}


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

        try:
            async with self.connect() as connection:
                cursor = await connection.execute("PRAGMA quick_check")
                rows = await cursor.fetchall()
        except DatabaseUnavailableError:
            raise
        except aiosqlite.Error as error:
            error_code = getattr(error, "sqlite_errorcode", None)

            if error_code in _INTEGRITY_ERROR_CODES:
                return False

            raise DatabaseUnavailableError(
                f"Unable to inspect SQLite database integrity: {self.database_path}"
            ) from error

        return len(rows) == 1 and str(rows[0][0]).casefold() == "ok"

    def exists(self) -> bool:
        """Return whether the configured SQLite database file exists."""
        return self.database_path.is_file()


class DatabaseMissingError(DatabaseUnavailableError):
    """Raised when Claviger's SQLite database does not exist."""
