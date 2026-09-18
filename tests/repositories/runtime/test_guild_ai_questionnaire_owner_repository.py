from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)

pytestmark = pytest.mark.asyncio


async def _database(
    tmp_path: Path,
) -> DatabaseConnection:
    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    await DatabaseSchema(
        database,
    ).initialize()
    return database


async def _workflow(
    database: DatabaseConnection,
    *,
    workflow_key: str,
    command_name: str,
) -> None:
    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_workflows (
                guild_id,
                workflow_key,
                command_name,
                command_description,
                title,
                policy_key,
                channel_mode,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                123,
                workflow_key,
                command_name,
                "Test command.",
                workflow_key.title(),
                workflow_key,
                "restricted",
                0,
                1,
            ),
        )
        await connection.commit()


async def test_set_moves_unique_owner_without_second_row(
    tmp_path: Path,
) -> None:
    """One guild always has at most one questionnaire owner row."""

    database = await _database(
        tmp_path,
    )
    await _workflow(
        database,
        workflow_key="gaming",
        command_name="gaming",
    )
    await _workflow(
        database,
        workflow_key="member",
        command_name="member",
    )

    repository = GuildAIQuestionnaireOwnerRepository(
        database,
    )

    await repository.set(
        guild_id=123,
        workflow_key="gaming",
    )
    assert await repository.get(123) == "gaming"

    await repository.set(
        guild_id=123,
        workflow_key="member",
    )
    assert await repository.get(123) == "member"

    async with database.connect() as connection:
        cursor = await connection.execute(
            """
            SELECT COUNT(*)
            FROM guild_ai_questionnaire_owner
            WHERE guild_id = 123
            """
        )
        row = await cursor.fetchone()

    assert row is not None
    assert int(row[0]) == 1


async def test_set_rejects_unknown_workflow(
    tmp_path: Path,
) -> None:
    """The database foreign key forbids an owner outside configured workflows."""

    database = await _database(
        tmp_path,
    )
    repository = GuildAIQuestionnaireOwnerRepository(
        database,
    )

    with pytest.raises(
        ValueError,
        match="existing workflow",
    ):
        await repository.set(
            guild_id=123,
            workflow_key="missing",
        )
