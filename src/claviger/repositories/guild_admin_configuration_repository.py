import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


class GuildAdminConfigurationRepository:
    """Persist guild-specific administrative Discord routing."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> GuildAdminConfiguration | None:
        """Return the administrative configuration for one guild."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        category_id,
                        command_channel_id,
                        activity_forum_id,
                        error_forum_id
                    FROM guild_admin_configuration
                    WHERE guild_id = ?
                    """,
                    (guild_id,),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read admin configuration for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return GuildAdminConfiguration(
            guild_id=int(row[0]),
            category_id=int(row[1]),
            command_channel_id=(int(row[2]) if row[2] is not None else None),
            activity_forum_id=int(row[3]),
            error_forum_id=(int(row[4]) if row[4] is not None else None),
        )

    async def save(
        self,
        configuration: GuildAdminConfiguration,
    ) -> None:
        """Create or replace one guild's administrative configuration."""

        self._validate(
            configuration,
        )

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    """
                    INSERT INTO guild_admin_configuration (
                        guild_id,
                        category_id,
                        command_channel_id,
                        activity_forum_id,
                        error_forum_id
                    )
                    VALUES (?, ?, ?, ?, ?)

                    ON CONFLICT (guild_id)
                    DO UPDATE SET
                        category_id = excluded.category_id,
                        command_channel_id = excluded.command_channel_id,
                        activity_forum_id = excluded.activity_forum_id,
                        error_forum_id = excluded.error_forum_id
                    """,
                    (
                        configuration.guild_id,
                        configuration.category_id,
                        configuration.command_channel_id,
                        configuration.activity_forum_id,
                        configuration.error_forum_id,
                    ),
                )

                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to persist admin configuration "
                f"for guild {configuration.guild_id}."
            ) from error

    def _validate(
        self,
        configuration: GuildAdminConfiguration,
    ) -> None:
        """Reject structurally impossible administrative configuration."""

        required_identifiers = {
            "guild_id": configuration.guild_id,
            "category_id": configuration.category_id,
            "activity_forum_id": configuration.activity_forum_id,
        }

        for name, value in required_identifiers.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        optional_identifiers = {
            "command_channel_id": configuration.command_channel_id,
            "error_forum_id": configuration.error_forum_id,
        }

        for name, value in optional_identifiers.items():
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be greater than zero when configured.")

        if (
            configuration.error_forum_id is not None
            and configuration.activity_forum_id == configuration.error_forum_id
        ):
            raise ValueError("Activity and error forums must be different.")

    def _ensure_database_exists(
        self,
    ) -> None:
        """Reject access that would implicitly create an SQLite database."""

        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
