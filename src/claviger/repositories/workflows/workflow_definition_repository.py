from collections.abc import Sequence
from typing import cast

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
    DatabaseUnavailableError,
)
from claviger.models.catalog_definition_model import CatalogDefinition
from claviger.models.context_definition_model import (
    ContextDefinition,
    ContextValueType,
)
from claviger.models.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowChannelMode,
    WorkflowContextBinding,
    WorkflowContextInteractionMode,
    WorkflowDefinition,
)


class WorkflowDefinitionRepository:
    """Read complete declarative workflow definitions from SQLite."""

    def __init__(
        self,
        database: DatabaseConnection,
    ) -> None:
        self.database = database

    async def get(
        self,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> WorkflowDefinition | None:
        """Return one workflow by its stable workflow key."""

        return await self._get_one(
            guild_id=guild_id,
            column_name="workflow_key",
            value=workflow_key,
        )

    async def get_by_command_name(
        self,
        *,
        guild_id: int,
        command_name: str,
    ) -> WorkflowDefinition | None:
        """Return the workflow routed to one Discord command name."""

        return await self._get_one(
            guild_id=guild_id,
            column_name="command_name",
            value=command_name,
        )

    async def list_for_guild(
        self,
        guild_id: int,
    ) -> tuple[WorkflowDefinition, ...]:
        """Return every workflow configured for one guild."""

        self._ensure_database_exists()

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    """
                    SELECT
                        guild_id,
                        workflow_key,
                        command_name,
                        command_description,
                        title,
                        description,
                        policy_key,
                        channel_mode,
                        category_id,
                        sort_order,
                        enabled
                    FROM guild_workflows
                    WHERE guild_id = ?
                    ORDER BY
                        sort_order,
                        workflow_key
                    """,
                    (guild_id,),
                )

                rows = await cursor.fetchall()

                return tuple(
                    [
                        await self._hydrate_workflow(
                            connection,
                            row,
                        )
                        for row in rows
                    ]
                )

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read workflows for guild {guild_id}."
            ) from error

    async def _get_one(
        self,
        *,
        guild_id: int,
        column_name: str,
        value: str,
    ) -> WorkflowDefinition | None:
        """Return one hydrated workflow using a trusted lookup column."""

        self._ensure_database_exists()

        if column_name not in {
            "workflow_key",
            "command_name",
        }:
            raise ValueError(f"Unsupported workflow lookup column: {column_name!r}.")

        try:
            async with self.database.connect() as connection:
                connection.row_factory = aiosqlite.Row

                cursor = await connection.execute(
                    f"""
                    SELECT
                        guild_id,
                        workflow_key,
                        command_name,
                        command_description,
                        title,
                        description,
                        policy_key,
                        channel_mode,
                        category_id,
                        sort_order,
                        enabled
                    FROM guild_workflows
                    WHERE guild_id = ?
                    AND {column_name} = ?
                    """,
                    (
                        guild_id,
                        value,
                    ),
                )

                row = await cursor.fetchone()

                if row is None:
                    return None

                return await self._hydrate_workflow(
                    connection,
                    row,
                )

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                f"Unable to read workflow for guild {guild_id}."
            ) from error

    async def _hydrate_workflow(
        self,
        connection: aiosqlite.Connection,
        row: aiosqlite.Row,
    ) -> WorkflowDefinition:
        """Load channels, contexts and catalogs belonging to one workflow."""

        guild_id = int(
            row["guild_id"],
        )

        workflow_key = str(
            row["workflow_key"],
        )

        channel_ids = await self._load_channel_ids(
            connection,
            guild_id=guild_id,
            workflow_key=workflow_key,
        )

        contexts = await self._load_contexts(
            connection,
            guild_id=guild_id,
            workflow_key=workflow_key,
        )

        catalogs = await self._load_catalogs(
            connection,
            guild_id=guild_id,
            workflow_key=workflow_key,
        )

        category_id = (
            int(
                row["category_id"],
            )
            if row["category_id"] is not None
            else None
        )

        return WorkflowDefinition(
            guild_id=guild_id,
            workflow_key=workflow_key,
            command_name=row["command_name"],
            command_description=row["command_description"],
            title=row["title"],
            description=row["description"],
            policy_key=row["policy_key"],
            channel_mode=cast(
                WorkflowChannelMode,
                row["channel_mode"],
            ),
            sort_order=row["sort_order"],
            enabled=bool(
                row["enabled"],
            ),
            channel_ids=channel_ids,
            catalogs=catalogs,
            category_id=category_id,
            contexts=contexts,
        )

    async def _load_channel_ids(
        self,
        connection: aiosqlite.Connection,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> tuple[int, ...]:
        """Load stable Discord channel IDs assigned to one workflow."""

        cursor = await connection.execute(
            """
            SELECT channel_id
            FROM guild_workflow_channels
            WHERE guild_id = ?
              AND workflow_key = ?
            ORDER BY channel_id
            """,
            (
                guild_id,
                workflow_key,
            ),
        )

        rows = await cursor.fetchall()

        return tuple(int(row["channel_id"]) for row in rows)

    async def _load_contexts(
        self,
        connection: aiosqlite.Connection,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> tuple[WorkflowContextBinding, ...]:
        """Load context definitions bound to one workflow."""

        cursor = await connection.execute(
            """
            SELECT
                context.guild_id,
                context.context_key,
                context.capability_key,
                context.value_type,
                context.role_id,
                context.label,
                context.description,
                context.sort_order AS context_sort_order,
                context.enabled AS context_enabled,

                binding.interaction_mode,
                binding.sort_order AS binding_sort_order,
                binding.enabled AS binding_enabled

            FROM guild_workflow_contexts AS binding

            INNER JOIN guild_context_definitions AS context
                ON context.guild_id = binding.guild_id
            AND context.context_key = binding.context_key

            WHERE binding.guild_id = ?
            AND binding.workflow_key = ?

            ORDER BY
                binding.sort_order,
                context.sort_order,
                context.context_key
            """,
            (
                guild_id,
                workflow_key,
            ),
        )

        rows: Sequence[aiosqlite.Row] = await cursor.fetchall()

        return tuple(
            WorkflowContextBinding(
                context=ContextDefinition(
                    guild_id=row["guild_id"],
                    context_key=row["context_key"],
                    capability_key=row["capability_key"],
                    value_type=cast(
                        ContextValueType,
                        row["value_type"],
                    ),
                    role_id=row["role_id"],
                    label=row["label"],
                    description=row["description"],
                    sort_order=row["context_sort_order"],
                    enabled=bool(row["context_enabled"]),
                ),
                interaction_mode=cast(
                    WorkflowContextInteractionMode,
                    row["interaction_mode"],
                ),
                sort_order=row["binding_sort_order"],
                enabled=bool(row["binding_enabled"]),
            )
            for row in rows
        )

    async def _load_catalogs(
        self,
        connection: aiosqlite.Connection,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> tuple[WorkflowCatalogBinding, ...]:
        """Load catalog definitions bound to one workflow."""

        cursor = await connection.execute(
            """
            SELECT
                catalog.guild_id,
                catalog.catalog_key,
                catalog.role_prefix,
                catalog.display_name,
                catalog.entry_name,
                catalog.description,
                catalog.sort_order AS catalog_sort_order,
                catalog.enabled AS catalog_enabled,

                binding.policy_key AS binding_policy_key,
                binding.sort_order AS binding_sort_order,
                binding.enabled AS binding_enabled

            FROM guild_workflow_catalogs AS binding

            INNER JOIN guild_catalogs AS catalog
                ON catalog.guild_id = binding.guild_id
               AND catalog.catalog_key = binding.catalog_key

            WHERE binding.guild_id = ?
              AND binding.workflow_key = ?

            ORDER BY
                binding.sort_order,
                catalog.sort_order,
                catalog.catalog_key
            """,
            (
                guild_id,
                workflow_key,
            ),
        )

        rows: Sequence[aiosqlite.Row] = await cursor.fetchall()

        return tuple(
            WorkflowCatalogBinding(
                catalog=CatalogDefinition(
                    guild_id=row["guild_id"],
                    catalog_key=row["catalog_key"],
                    role_prefix=row["role_prefix"],
                    display_name=row["display_name"],
                    entry_name=row["entry_name"],
                    description=row["description"],
                    sort_order=row["catalog_sort_order"],
                    enabled=bool(row["catalog_enabled"]),
                ),
                policy_key=row["binding_policy_key"],
                sort_order=row["binding_sort_order"],
                enabled=bool(row["binding_enabled"]),
            )
            for row in rows
        )

    def _ensure_database_exists(
        self,
    ) -> None:
        """Reject reads that would implicitly create an empty SQLite file."""

        if self.database.exists():
            return

        raise DatabaseMissingError(
            f"SQLite database does not exist: {self.database.database_path}"
        )
