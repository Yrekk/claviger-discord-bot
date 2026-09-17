from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
)
from claviger.policies.guild_policy import GuildPolicyOverrides


class GuildPolicyPersistenceRetiredError(RuntimeError):
    """Reject writes to the V1 guild-policy persistence removed by schema V11."""


class GuildPolicyRepository:
    """Compatibility boundary for retired V1 guild policy persistence.

    Schema V11 no longer stores workflow-specific policy fields in
    ``guild_settings``. Runtime fallback policy now comes from code snapshots,
    while generic workflow configuration is persisted through its dedicated
    repositories. This adapter remains temporarily so older inspection code can
    resolve a snapshot without querying columns that no longer exist.
    """

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> GuildPolicyOverrides | None:
        """Return no SQLite overrides because V11 retired their storage."""

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

        return None

    async def save(
        self,
        guild_id: int,
        overrides: GuildPolicyOverrides,
    ) -> None:
        """Reject obsolete V1 policy persistence after schema V11."""

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

        raise GuildPolicyPersistenceRetiredError(
            "Guild policy overrides were retired by schema V11; "
            "use generic ADMIN/workflow configuration instead."
        )
