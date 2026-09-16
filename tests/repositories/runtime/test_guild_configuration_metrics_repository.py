import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.repositories.runtime.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)


@pytest.mark.asyncio
async def test_metrics_repository_counts_only_enabled_guild_configuration(
    tmp_path,
) -> None:
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    async with database.connect() as connection:
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
                sort_order,
                enabled
            )
            VALUES
                (123, 'one', 'one', 'One', 'One', NULL, 'one', 'restricted', 0, 1),
                (123, 'two', 'two', 'Two', 'Two', NULL, 'two', 'restricted', 1, 0),
                (999, 'other', 'other', 'Other', 'Other', NULL, 'other', 'restricted', 0, 1)
            """
        )

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
            VALUES
                (123, 'catalog-one', 'one-', 'One', 'option', NULL, 0, 1),
                (123, 'catalog-two', 'two-', 'Two', 'option', NULL, 1, 0)
            """
        )

        await connection.execute(
            """
            INSERT INTO guild_context_definitions (
                guild_id,
                context_key,
                capability_key,
                value_type,
                role_id,
                label,
                description,
                sort_order,
                enabled
            )
            VALUES
                (123, 'context-one', 'capability-one', 'boolean', 1001, 'One', NULL, 0, 1),
                (123, 'context-two', 'capability-two', 'boolean', 1002, 'Two', NULL, 1, 0)
            """
        )

        await connection.commit()

    repository = GuildConfigurationMetricsRepository(
        database,
    )

    metrics = await repository.get(
        123,
    )

    assert metrics.workflow_count == 1
    assert metrics.catalog_count == 1
    assert metrics.context_count == 1
