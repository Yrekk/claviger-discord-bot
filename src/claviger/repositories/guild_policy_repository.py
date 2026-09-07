import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.policies.guild_policy import GuildPolicyOverrides


class GuildPolicyRepository:
    """Persist guild-specific policy overrides in SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> GuildPolicyOverrides | None:
        """Return policy overrides for a guild, or None when none exist."""

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        member_role_name,
                        adult_role_name,
                        member_interest_prefix,
                        adult_access_prefix,
                        salutations_channel_name,
                        adult_access_channel_name,
                        role_management_enabled,
                        adult_access_enabled
                    FROM guild_settings
                    WHERE guild_id = ?
                    """,
                    (guild_id,),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read guild policy for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return GuildPolicyOverrides(
            member_role_name=row["member_role_name"],
            adult_role_name=row["adult_role_name"],
            member_interest_prefix=row["member_interest_prefix"],
            adult_access_prefix=row["adult_access_prefix"],
            salutations_channel_name=row["salutations_channel_name"],
            adult_access_channel_name=row["adult_access_channel_name"],
            role_management_enabled=self._to_optional_bool(
                row["role_management_enabled"]
            ),
            adult_access_enabled=self._to_optional_bool(row["adult_access_enabled"]),
        )

    async def save(
        self,
        guild_id: int,
        overrides: GuildPolicyOverrides,
    ) -> None:
        """Create or replace all policy overrides for a guild."""

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    """
                    INSERT INTO guild_settings (
                        guild_id,
                        member_role_name,
                        adult_role_name,
                        member_interest_prefix,
                        adult_access_prefix,
                        salutations_channel_name,
                        adult_access_channel_name,
                        role_management_enabled,
                        adult_access_enabled
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        member_role_name = excluded.member_role_name,
                        adult_role_name = excluded.adult_role_name,
                        member_interest_prefix =
                            excluded.member_interest_prefix,
                        adult_access_prefix =
                            excluded.adult_access_prefix,
                        salutations_channel_name =
                            excluded.salutations_channel_name,
                        adult_access_channel_name =
                            excluded.adult_access_channel_name,
                        role_management_enabled =
                            excluded.role_management_enabled,
                        adult_access_enabled =
                            excluded.adult_access_enabled
                    """,
                    (
                        guild_id,
                        overrides.member_role_name,
                        overrides.adult_role_name,
                        overrides.member_interest_prefix,
                        overrides.adult_access_prefix,
                        overrides.salutations_channel_name,
                        overrides.adult_access_channel_name,
                        overrides.role_management_enabled,
                        overrides.adult_access_enabled,
                    ),
                )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to save guild policy for guild {guild_id}."
            ) from error

    @staticmethod
    def _to_optional_bool(
        value: int | None,
    ) -> bool | None:
        """Convert a nullable SQLite integer into a nullable boolean."""

        if value is None:
            return None

        return bool(value)
