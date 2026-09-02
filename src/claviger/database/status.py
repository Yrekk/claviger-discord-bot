from dataclasses import dataclass
from enum import StrEnum

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseUnavailableError,
)
from claviger.database.schema import (
    CURRENT_SCHEMA_VERSION,
    DatabaseSchema,
)


class DatabaseState(StrEnum):
    """Possible states of Claviger's SQLite database."""

    MISSING = "missing"
    UNINITIALIZED = "uninitialized"
    READY = "ready"
    MIGRATION_REQUIRED = "migration_required"
    TOO_NEW = "too_new"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class DatabaseStatus:
    """Describe the current state of Claviger's database."""

    state: DatabaseState
    current_version: int | None
    target_version: int


class DatabaseStatusService:
    """Inspect Claviger's database without modifying it."""

    def __init__(
        self,
        database: DatabaseConnection,
        schema: DatabaseSchema,
    ) -> None:
        self.database = database
        self.schema = schema

    async def check(self) -> DatabaseStatus:
        """Return the current database state without changing it."""

        if not self.database.exists():
            return DatabaseStatus(
                state=DatabaseState.MISSING,
                current_version=None,
                target_version=CURRENT_SCHEMA_VERSION,
            )

        if not await self.database.is_available():
            return DatabaseStatus(
                state=DatabaseState.UNAVAILABLE,
                current_version=None,
                target_version=CURRENT_SCHEMA_VERSION,
            )

        try:
            current_version = await self.schema.get_version()
        except (DatabaseUnavailableError, aiosqlite.Error):
            return DatabaseStatus(
                state=DatabaseState.UNAVAILABLE,
                current_version=None,
                target_version=CURRENT_SCHEMA_VERSION,
            )

        if current_version == 0:
            state = DatabaseState.UNINITIALIZED
        elif current_version < CURRENT_SCHEMA_VERSION:
            state = DatabaseState.MIGRATION_REQUIRED
        elif current_version > CURRENT_SCHEMA_VERSION:
            state = DatabaseState.TOO_NEW
        else:
            state = DatabaseState.READY

        return DatabaseStatus(
            state=state,
            current_version=current_version,
            target_version=CURRENT_SCHEMA_VERSION,
        )
