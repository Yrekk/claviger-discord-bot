import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)


class GuildAIQuestionnaireOwnerRepository:
    """Persist the unique workflow owning the guild AI preference question."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> str | None:
        """Return the owner workflow key for one guild, or None when unset."""

        self._validate_guild_id(
            guild_id,
        )
        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    SELECT workflow_key
                    FROM guild_ai_questionnaire_owner
                    WHERE guild_id = ?
                    """,
                    (guild_id,),
                )
                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to read AI questionnaire ownership "
                f"for guild {guild_id}."
            ) from error

        if row is None:
            return None

        return str(
            row[0],
        )

    async def set(
        self,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> None:
        """Atomically assign or move the unique owner to one workflow."""

        self._validate_guild_id(
            guild_id,
        )

        normalized_key = workflow_key.strip()

        if not normalized_key:
            raise ValueError("Workflow key cannot be empty.")

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute(
                    """
                    INSERT INTO guild_ai_questionnaire_owner (
                        guild_id,
                        workflow_key
                    )
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        workflow_key = excluded.workflow_key
                    """,
                    (
                        guild_id,
                        normalized_key,
                    ),
                )
                await connection.commit()

        except aiosqlite.IntegrityError as error:
            raise ValueError(
                "AI questionnaire owner must reference an existing workflow "
                "from the same guild."
            ) from error
        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to persist AI questionnaire ownership "
                f"for guild {guild_id}."
            ) from error

    def _ensure_database_exists(
        self,
    ) -> None:
        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )

    @staticmethod
    def _validate_guild_id(
        guild_id: int,
    ) -> None:
        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")
