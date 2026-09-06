from claviger.database.connection import DatabaseConnection
from claviger.models.adult_access import AdultAccess
from claviger.repositories.role_channel_catalog_repository import (
    RoleChannelCatalogRepository,
)


class AdultAccessNotFoundError(RuntimeError):
    """Raised when a requested adult access does not exist."""


class AccessCatalogRepository(
    RoleChannelCatalogRepository[AdultAccess],
):
    """Persist the adult access catalog in SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        super().__init__(
            database,
            table_name="guild_adult_accesses",
            key_column="access_key",
            entry_type=AdultAccess,
            entry_label="adult access",
            not_found_error=AdultAccessNotFoundError,
        )

    async def create_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        access_key: str,
        channel_id: int,
        channel_name: str,
    ) -> AdultAccess:
        """Create a newly discovered Discord adult access."""

        return await super().create_discovered(
            guild_id=guild_id,
            role_id=role_id,
            role_name=role_name,
            catalog_key=access_key,
            channel_id=channel_id,
            channel_name=channel_name,
        )

    async def refresh_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        access_key: str,
        channel_id: int,
        channel_name: str,
    ) -> None:
        """Refresh Discord-owned adult access data."""

        await super().refresh_discovered(
            guild_id=guild_id,
            role_id=role_id,
            role_name=role_name,
            catalog_key=access_key,
            channel_id=channel_id,
            channel_name=channel_name,
        )
