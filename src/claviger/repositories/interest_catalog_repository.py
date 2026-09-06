import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.member_interest import MemberInterest


class MemberInterestNotFoundError(RuntimeError):
    """Raised when a requested member interest does not exist."""


class InterestCatalogRepository:
    """Persist the member interest catalog in SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def list_for_guild(
        self,
        guild_id: int,
    ) -> list[MemberInterest]:
        """Return every known member interest for a guild."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM guild_member_interests
                    WHERE guild_id = ?
                    ORDER BY
                        sort_order,
                        role_name,
                        role_id
                    """,
                    (guild_id,),
                )

                rows = await cursor.fetchall()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read member interests for guild {guild_id}."
            ) from error

        return [self._to_member_interest(row) for row in rows]

    async def get(
        self,
        guild_id: int,
        role_id: int,
    ) -> MemberInterest | None:
        """Return one member interest by its stable Discord role identity."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM guild_member_interests
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        guild_id,
                        role_id,
                    ),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to read member interest {role_id} for guild {guild_id}.")
            ) from error

        if row is None:
            return None

        return self._to_member_interest(row)

    async def create_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        interest_key: str,
        channel_id: int,
        channel_name: str,
    ) -> MemberInterest:
        """Create a newly discovered Discord member interest."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    """
                    INSERT INTO guild_member_interests (
                        guild_id,
                        role_id,
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        guild_id,
                        role_id,
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name,
                    ),
                )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to create member interest {role_id} for guild {guild_id}.")
            ) from error

        interest = await self.get(
            guild_id,
            role_id,
        )

        if interest is None:
            raise DatabaseUnavailableError(
                (
                    "Member interest was created but could not be "
                    f"reloaded for guild {guild_id}, role {role_id}."
                )
            )

        return interest

    async def refresh_discovered(
        self,
        guild_id: int,
        role_id: int,
        role_name: str,
        interest_key: str,
        channel_id: int,
        channel_name: str,
    ) -> None:
        """Refresh Discord-owned data without changing human metadata."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    UPDATE guild_member_interests
                    SET
                        role_name = ?,
                        interest_key = ?,
                        channel_id = ?,
                        channel_name = ?,
                        discord_present = 1,
                        role_manageable= 1,
                        channel_present = 1,
                        mapping_valid = 1,
                        matches_policy = 1
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise MemberInterestNotFoundError(
                        (
                            "Member interest does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except MemberInterestNotFoundError:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to refresh member interest {role_id} for guild {guild_id}.")
            ) from error

    async def update_sync_state(
        self,
        guild_id: int,
        role_id: int,
        *,
        discord_present: bool,
        role_manageable: bool,
        channel_present: bool,
        mapping_valid: bool,
        matches_policy: bool,
    ) -> None:
        """Update synchronization state without erasing stored identities."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    UPDATE guild_member_interests
                    SET
                        discord_present = ?,
                        role_manageable  = ?,
                        channel_present = ?,
                        mapping_valid = ?,
                        matches_policy = ?
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise MemberInterestNotFoundError(
                        (
                            "Member interest does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except MemberInterestNotFoundError:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    "Unable to update synchronization state for "
                    f"member interest {role_id} in guild {guild_id}."
                )
            ) from error

    async def get_next_incomplete(
        self,
        guild_id: int,
    ) -> MemberInterest | None:
        """Return the next usable interest missing required human metadata."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        role_id,
                        role_name,
                        interest_key,
                        channel_id,
                        channel_name,
                        label,
                        description,
                        emoji,
                        sort_order,
                        enabled,
                        discord_present,
                        role_manageable,
                        channel_present,
                        mapping_valid,
                        matches_policy
                    FROM guild_member_interests
                    WHERE guild_id = ?
                      AND enabled = 1
                      AND discord_present = 1
                      AND channel_present = 1
                      AND matches_policy = 1
                      AND (
                          label IS NULL
                          OR description IS NULL
                      )
                    ORDER BY
                        sort_order,
                        role_name,
                        role_id
                    LIMIT 1
                    """,
                    (guild_id,),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to find incomplete member interests for guild {guild_id}.")
            ) from error

        if row is None:
            return None

        return self._to_member_interest(row)

    async def update_metadata(
        self,
        guild_id: int,
        role_id: int,
        *,
        label: str,
        description: str,
        emoji: str | None,
    ) -> None:
        """Update human-managed metadata for one member interest."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    UPDATE guild_member_interests
                    SET
                        label = ?,
                        description = ?,
                        emoji = ?
                    WHERE guild_id = ?
                      AND role_id = ?
                    """,
                    (
                        label,
                        description,
                        emoji,
                        guild_id,
                        role_id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise MemberInterestNotFoundError(
                        (
                            "Member interest does not exist: "
                            f"guild={guild_id}, role={role_id}."
                        )
                    )

                await connection.commit()

        except MemberInterestNotFoundError:
            raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (
                    "Unable to update metadata for member interest "
                    f"{role_id} in guild {guild_id}."
                )
            ) from error

    def _ensure_database_exists(self) -> None:
        """Reject repository access without implicitly creating SQLite."""

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

    @staticmethod
    def _to_member_interest(
        row: aiosqlite.Row,
    ) -> MemberInterest:
        """Convert one SQLite row into the domain model."""

        return MemberInterest(
            guild_id=row["guild_id"],
            role_id=row["role_id"],
            role_name=row["role_name"],
            interest_key=row["interest_key"],
            channel_id=row["channel_id"],
            channel_name=row["channel_name"],
            label=row["label"],
            description=row["description"],
            emoji=row["emoji"],
            sort_order=row["sort_order"],
            enabled=bool(row["enabled"]),
            discord_present=bool(row["discord_present"]),
            role_manageable=bool(row["role_manageable"]),
            channel_present=bool(row["channel_present"]),
            mapping_valid=bool(row["mapping_valid"]),
            matches_policy=bool(row["matches_policy"]),
        )
