import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.workflows.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
class WorkflowConfigurationConflictError(RuntimeError):
    """Raised when workflow configuration conflicts with persisted identities."""


class WorkflowConfigurationRepository:
    """Persist resolved workflow configuration as one SQLite transaction."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def save(
        self,
        configuration: ResolvedWorkflowConfiguration,
    ) -> None:
        """Persist one resolved workflow and its declarative bindings atomically."""

        self._validate_resolved_configuration(
            configuration,
        )

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                await connection.execute("BEGIN IMMEDIATE")

                catalog_key = await self._resolve_catalog_key(
                    connection,
                    configuration=configuration,
                )

                await self._save_catalog(
                    connection,
                    configuration=configuration,
                    catalog_key=catalog_key,
                )

                await self._save_workflow(
                    connection,
                    configuration=configuration,
                )

                # Creation is intentionally additive for execution channels and
                # catalogs. Existing complex workflows may already contain
                # several bindings; configuration must not silently erase them.
                await self._bind_execution_channel(
                    connection,
                    configuration=configuration,
                )

                await self._bind_catalog(
                    connection,
                    configuration=configuration,
                    catalog_key=catalog_key,
                )
                await connection.commit()

        except WorkflowConfigurationConflictError:
            raise

        except aiosqlite.IntegrityError as error:
            raise WorkflowConfigurationConflictError(
                "Workflow configuration conflicts with persisted guild data."
            ) from error

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                "Unable to persist workflow configuration "
                f"{configuration.workflow_key!r} "
                f"for guild {configuration.guild_id}."
            ) from error

    async def _resolve_catalog_key(
        self,
        connection: aiosqlite.Connection,
        *,
        configuration: ResolvedWorkflowConfiguration,
    ) -> str:
        """Reuse a catalog already owning the requested role prefix."""

        cursor = await connection.execute(
            """
            SELECT catalog_key
            FROM guild_catalogs
            WHERE guild_id = ?
              AND role_prefix = ?
            """,
            (
                configuration.guild_id,
                configuration.questionnaire_role_prefix,
            ),
        )

        row = await cursor.fetchone()

        if row is not None:
            return str(
                row[0],
            )

        # New workflows receive a stable internal key. Human-readable labels
        # remain independent from this database identity.
        return f"{configuration.workflow_key}-questionnaire"

    @staticmethod
    async def _save_catalog(
        connection: aiosqlite.Connection,
        *,
        configuration: ResolvedWorkflowConfiguration,
        catalog_key: str,
    ) -> None:
        """Create or refresh the workflow's primary questionnaire catalog."""

        await connection.execute(
            """
            INSERT INTO guild_catalogs (
                guild_id,
                catalog_key,
                role_prefix,
                display_name,
                entry_name,
                description,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT (
                guild_id,
                catalog_key
            )
            DO UPDATE SET
                role_prefix = excluded.role_prefix,
                display_name = excluded.display_name,
                entry_name = excluded.entry_name,
                description = excluded.description,
                enabled = excluded.enabled
            """,
            (
                configuration.guild_id,
                catalog_key,
                configuration.questionnaire_role_prefix,
                configuration.title,
                "option",
                configuration.description,
                0,
                1,
            ),
        )

    @staticmethod
    async def _save_workflow(
        connection: aiosqlite.Connection,
        *,
        configuration: ResolvedWorkflowConfiguration,
    ) -> None:
        """Create or refresh the stable workflow definition."""

        await connection.execute(
            """
            INSERT INTO guild_workflows (
                guild_id,
                workflow_key,
                command_name,
                command_description,
                title,
                description,
                policy_key,
                channel_mode,
                category_id,
                management_channel_id,
                primary_role_id,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT (
                guild_id,
                workflow_key
            )
            DO UPDATE SET
                command_name = excluded.command_name,
                command_description = excluded.command_description,
                title = excluded.title,
                description = excluded.description,
                category_id = excluded.category_id,
                management_channel_id = excluded.management_channel_id,
                primary_role_id = excluded.primary_role_id,
                enabled = excluded.enabled
            """,
            (
                configuration.guild_id,
                configuration.workflow_key,
                configuration.command_name,
                configuration.command_description,
                configuration.title,
                configuration.description,
                # policy_key predates the generic configuration UI. New generic
                # workflows use their stable workflow identity as their initial
                # internal policy identity. Existing workflows preserve their
                # original policy_key through the conflict-update clause above.
                configuration.workflow_key,
                "restricted",
                configuration.category_id,
                configuration.management_channel_id,
                configuration.primary_role_id,
                0,
                1,
            ),
        )

    @staticmethod
    async def _bind_execution_channel(
        connection: aiosqlite.Connection,
        *,
        configuration: ResolvedWorkflowConfiguration,
    ) -> None:
        """Bind the selected execution channel without deleting existing routes."""

        await connection.execute(
            """
            INSERT OR IGNORE INTO guild_workflow_channels (
                guild_id,
                workflow_key,
                channel_id
            )
            VALUES (?, ?, ?)
            """,
            (
                configuration.guild_id,
                configuration.workflow_key,
                configuration.execution_channel_id,
            ),
        )

    @staticmethod
    async def _bind_catalog(
        connection: aiosqlite.Connection,
        *,
        configuration: ResolvedWorkflowConfiguration,
        catalog_key: str,
    ) -> None:
        """Bind the questionnaire catalog without erasing complementary catalogs."""

        await connection.execute(
            """
            INSERT INTO guild_workflow_catalogs (
                guild_id,
                workflow_key,
                catalog_key,
                policy_key,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?)

            ON CONFLICT (
                guild_id,
                workflow_key,
                catalog_key
            )
            DO UPDATE SET
                enabled = excluded.enabled
            """,
            (
                configuration.guild_id,
                configuration.workflow_key,
                catalog_key,
                None,
                0,
                1,
            ),
        )

    @staticmethod
    def _validate_resolved_configuration(
        configuration: ResolvedWorkflowConfiguration,
    ) -> None:
        """Reject unresolved or cross-layer-invalid Discord identities."""

        positive_ids = (
            configuration.guild_id,
            configuration.category_id,
            configuration.management_channel_id,
            configuration.execution_channel_id,
            configuration.primary_role_id,
        )

        if any(resource_id <= 0 for resource_id in positive_ids):
            raise ValueError(
                "Resolved workflow Discord IDs must all be greater than zero."
            )

        if configuration.management_channel_id == configuration.execution_channel_id:
            raise ValueError("Management and execution channels must be different.")

    def _ensure_database_exists(
        self,
    ) -> None:
        """Reject persistence that would implicitly create an empty SQLite file."""

        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
