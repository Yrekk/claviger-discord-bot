from claviger.database.connection import DatabaseConnection
from claviger.models.member_interest import MemberInterest
from claviger.repositories.role_channel_catalog_repository import (
    RoleChannelCatalogRepository,
)


class MemberInterestNotFoundError(RuntimeError):
    """Raised when a requested member interest does not exist."""


class InterestCatalogRepository(
    RoleChannelCatalogRepository[MemberInterest],
):
    """Persist the member interest catalog in SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        super().__init__(
            database,
            table_name="guild_member_interests",
            key_column="interest_key",
            entry_type=MemberInterest,
            entry_label="member interest",
            not_found_error=MemberInterestNotFoundError,
        )

    async def create_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        interest_key: str,
        channel_id: int,
        channel_name: str,
        *,
        role_manageable: bool = True,
    ) -> MemberInterest:
        """Create a newly discovered Discord member interest."""

        return await super().create_discovered(
            guild_id=guild_id,
            role_id=role_id,
            role_name=role_name,
            catalog_key=interest_key,
            channel_id=channel_id,
            channel_name=channel_name,
            role_manageable=role_manageable,
        )

    async def refresh_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        interest_key: str,
        channel_id: int,
        channel_name: str,
        *,
        role_manageable: bool = True,
    ) -> None:
        """Refresh Discord-owned member interest data."""

        await super().refresh_discovered(
            guild_id=guild_id,
            role_id=role_id,
            role_name=role_name,
            catalog_key=interest_key,
            channel_id=channel_id,
            channel_name=channel_name,
            role_manageable=role_manageable,
        )
