import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
)


class GuildAIConfigurationRepository:
    """Persist guild-scoped AI settings without owning historical guild policy."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> GuildAIConfiguration | None:
        """Return the persisted AI configuration for one guild.

        Args:
            guild_id:
                Discord guild snowflake whose AI configuration must be loaded.

        Returns:
            GuildAIConfiguration | None:
                The stored AI configuration. ``None`` means that no
                ``guild_settings`` row exists for the guild; a row whose
                ``ai_enabled`` value is NULL is returned as an explicit
                UNCONFIGURED configuration instead.

        Raises:
            DatabaseMissingError:
                If the SQLite database file does not exist.
            DatabaseUnavailableError:
                If SQLite cannot read the configuration.
        """

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
                        ai_enabled,
                        ai_role_id
                    FROM guild_settings
                    WHERE guild_id = ?
                    """,
                    (guild_id,),
                )
                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read AI configuration for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return GuildAIConfiguration(
            guild_id=guild_id,
            ai_enabled=self._to_optional_bool(row["ai_enabled"]),
            ai_role_id=row["ai_role_id"],
        )

    async def save(
        self,
        configuration: GuildAIConfiguration,
    ) -> None:
        """Create or replace only the AI-owned columns for one guild.

        Existing policy values stored in the same ``guild_settings`` row are
        intentionally left untouched. This keeps the physical SQLite layout
        independent from the application ownership boundary between guild
        policy and AI configuration.

        Args:
            configuration:
                Complete AI configuration to persist for one guild.

        Raises:
            DatabaseMissingError:
                If the SQLite database file does not exist.
            DatabaseUnavailableError:
                If SQLite rejects or cannot persist the configuration.
        """

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
                        ai_enabled,
                        ai_role_id
                    )
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        ai_enabled = excluded.ai_enabled,
                        ai_role_id = excluded.ai_role_id
                    """,
                    (
                        configuration.guild_id,
                        configuration.ai_enabled,
                        configuration.ai_role_id,
                    ),
                )
                await connection.commit()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to save AI configuration for guild "
                f"{configuration.guild_id}."
            ) from error

    @staticmethod
    def _to_optional_bool(
        value: int | None,
    ) -> bool | None:
        """Convert a nullable SQLite integer into a nullable boolean."""

        if value is None:
            return None

        return bool(value)
