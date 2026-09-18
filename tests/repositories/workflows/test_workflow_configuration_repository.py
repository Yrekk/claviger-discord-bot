from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.workflows.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)

pytestmark = pytest.mark.asyncio


async def _repository(
    tmp_path: Path,
) -> tuple[
    DatabaseConnection,
    WorkflowConfigurationRepository,
]:
    """Create one initialized V10 workflow configuration repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await DatabaseSchema(
        database,
    ).initialize()

    return (
        database,
        WorkflowConfigurationRepository(
            database,
        ),
    )


def _configuration() -> ResolvedWorkflowConfiguration:
    """Create one deterministic resolved workflow configuration."""

    return ResolvedWorkflowConfiguration(
        guild_id=123,
        workflow_key="member",
        title="Membre",
        description="Gestion du profil membre.",
        command_name="membre",
        command_description="Gère ton profil membre.",
        category_id=100,
        management_channel_id=200,
        execution_channel_id=201,
        primary_role_id=300,
        questionnaire_role_prefix="interest-",
    )


async def test_save_persists_generic_workflow_structure(
    tmp_path: Path,
) -> None:
    """Persist the workflow, questionnaire catalog and execution routing."""

    database, repository = await _repository(
        tmp_path,
    )

    await repository.save(
        _configuration(),
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT
                workflow_key,
                command_name,
                policy_key,
                category_id,
                management_channel_id,
                primary_role_id
            FROM guild_workflows
            WHERE guild_id = ?
            """,
            (123,),
        )

        workflow = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT role_prefix
            FROM guild_catalogs
            WHERE guild_id = ?
            """,
            (123,),
        )

        catalog = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT channel_id
            FROM guild_workflow_channels
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        execution_channel = await cursor.fetchone()

    assert workflow == (
        "member",
        "membre",
        "member",
        100,
        200,
        300,
    )

    assert catalog == ("interest-",)

    assert execution_channel == (201,)





async def test_save_is_idempotent_for_same_resolved_configuration(
    tmp_path: Path,
) -> None:
    """Allow a frontend or coordinator to safely resubmit the same configuration."""

    database, repository = await _repository(
        tmp_path,
    )

    configuration = _configuration()

    await repository.save(
        configuration,
    )

    await repository.save(
        configuration,
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_workflows
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        workflow_count = await cursor.fetchone()

        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_workflow_channels
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        channel_count = await cursor.fetchone()

    assert workflow_count == (1,)

    assert channel_count == (1,)
