from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.resolved_workflow_configuration_model import (
    ResolvedWorkflowConfiguration,
)
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationConflictError,
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


def _configuration(
    *,
    ai_preference_role_id: int | None = None,
) -> ResolvedWorkflowConfiguration:
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
        ai_preference_role_id=ai_preference_role_id,
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


async def test_save_creates_and_binds_ai_preference_context(
    tmp_path: Path,
) -> None:
    """Persist AI support through the existing context-capability model."""

    database, repository = await _repository(
        tmp_path,
    )

    await repository.save(
        _configuration(
            ai_preference_role_id=301,
        )
    )

    assert (
        await repository.get_ai_preference_role_id(
            123,
        )
        == 301
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT
                definition.capability_key,
                definition.role_id,
                binding.interaction_mode
            FROM guild_workflow_contexts AS binding

            INNER JOIN guild_context_definitions AS definition
                ON definition.guild_id = binding.guild_id
               AND definition.context_key = binding.context_key

            WHERE binding.guild_id = ?
              AND binding.workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        row = await cursor.fetchone()

    assert row == (
        "ai_preference",
        301,
        "editable",
    )


async def test_disabling_ai_unbinds_workflow_without_deleting_shared_context(
    tmp_path: Path,
) -> None:
    """Disable AI locally while preserving the guild-wide capability definition."""

    database, repository = await _repository(
        tmp_path,
    )

    await repository.save(
        _configuration(
            ai_preference_role_id=301,
        )
    )

    await repository.save(
        _configuration(
            ai_preference_role_id=None,
        )
    )

    # The shared capability remains available for another workflow.
    assert (
        await repository.get_ai_preference_role_id(
            123,
        )
        == 301
    )

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_workflow_contexts
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        row = await cursor.fetchone()

    assert row == (0,)


async def test_save_rejects_replacing_shared_ai_preference_role(
    tmp_path: Path,
) -> None:
    """Prevent one workflow from silently changing another workflow's AI role."""

    _, repository = await _repository(
        tmp_path,
    )

    await repository.save(
        _configuration(
            ai_preference_role_id=301,
        )
    )

    with pytest.raises(
        WorkflowConfigurationConflictError,
        match="another role",
    ):
        await repository.save(
            ResolvedWorkflowConfiguration(
                guild_id=123,
                workflow_key="adult",
                title="Adulte",
                description=None,
                command_name="noctis",
                command_description="Gère les accès adultes.",
                category_id=400,
                management_channel_id=401,
                execution_channel_id=402,
                primary_role_id=403,
                questionnaire_role_prefix="access-",
                ai_preference_role_id=999,
            )
        )


async def test_save_is_idempotent_for_same_resolved_configuration(
    tmp_path: Path,
) -> None:
    """Allow a frontend or coordinator to safely resubmit the same configuration."""

    database, repository = await _repository(
        tmp_path,
    )

    configuration = _configuration(
        ai_preference_role_id=301,
    )

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
