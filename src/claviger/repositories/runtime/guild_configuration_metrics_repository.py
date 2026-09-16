import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.runtime.guild_configuration_metrics_model import (
    GuildConfigurationMetrics,
)


class GuildConfigurationMetricsRepository:
    """Read small configuration counters used by administrative diagnostics."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        guild_id: int,
    ) -> GuildConfigurationMetrics:
        """Return enabled workflow, catalog and context counts for one guild."""

        if guild_id <= 0:
            raise ValueError("Guild ID must be greater than zero.")

        if not self.database.exists():
            raise DatabaseMissingError(
                f"SQLite database does not exist: {self.database.database_path}"
            )

        try:
            async with self.database.connect() as connection:
                cursor = await connection.execute(
                    """
                    SELECT
                        (
                            SELECT COUNT(*)
                            FROM guild_workflows
                            WHERE guild_id = ?
                              AND enabled = 1
                        ),
                        (
                            SELECT COUNT(*)
                            FROM guild_catalogs
                            WHERE guild_id = ?
                              AND enabled = 1
                        ),
                        (
                            SELECT COUNT(*)
                            FROM guild_context_definitions
                            WHERE guild_id = ?
                              AND enabled = 1
                        )
                    """,
                    (
                        guild_id,
                        guild_id,
                        guild_id,
                    ),
                )

                row = await cursor.fetchone()

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read configuration metrics for guild {guild_id}."
            ) from error

        if row is None:
            raise DatabaseUnavailableError(
                f"Configuration metrics query returned no row for guild {guild_id}."
            )

        return GuildConfigurationMetrics(
            workflow_count=int(row[0]),
            catalog_count=int(row[1]),
            context_count=int(row[2]),
        )
