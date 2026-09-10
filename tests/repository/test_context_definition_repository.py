from pathlib import Path

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
)
from claviger.database.schema import DatabaseSchema
from claviger.models.context_definition_model import ContextDefinition
from claviger.repositories.context_definition_repository import (
    ContextDefinitionRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_repository(
    tmp_path: Path,
) -> tuple[
    DatabaseConnection,
    ContextDefinitionRepository,
]:
    """Create an initialized context definition repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return (
        database,
        ContextDefinitionRepository(
            database,
        ),
    )


async def _insert_context(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    context_key: str = "ai-content",
    capability_key: str = "ai_preference",
    role_id: int = 111,
    label: str = "Allow AI-generated content?",
    description: str | None = None,
    sort_order: int = 0,
    enabled: bool = True,
) -> None:
    """Insert one context definition directly into SQLite."""

    async with database.connect() as connection:
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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                context_key,
                capability_key,
                "boolean",
                role_id,
                label,
                description,
                sort_order,
                enabled,
            ),
        )

        await connection.commit()


async def test_get_returns_none_for_unknown_context(
    tmp_path: Path,
) -> None:
    """Return None when the requested context does not exist."""

    _, repository = await _create_repository(
        tmp_path,
    )

    result = await repository.get(
        guild_id=123,
        context_key="missing",
    )

    assert result is None


async def test_get_returns_complete_context_definition(
    tmp_path: Path,
) -> None:
    """Load one complete context definition."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_context(
        database,
        context_key="ai-content",
        capability_key="ai_preference",
        role_id=987654321,
        label="Allow AI-generated content?",
        description="Controls AI-specific role variants.",
        sort_order=10,
        enabled=False,
    )

    result = await repository.get(
        guild_id=123,
        context_key="ai-content",
    )

    assert result == ContextDefinition(
        guild_id=123,
        context_key="ai-content",
        capability_key="ai_preference",
        value_type="boolean",
        role_id=987654321,
        label="Allow AI-generated content?",
        description="Controls AI-specific role variants.",
        sort_order=10,
        enabled=False,
    )


async def test_list_for_guild_orders_contexts(
    tmp_path: Path,
) -> None:
    """Return contexts using their configured order."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_context(
        database,
        context_key="notifications",
        capability_key="notifications_enabled",
        role_id=222,
        sort_order=20,
    )

    await _insert_context(
        database,
        context_key="ai-content",
        capability_key="ai_preference",
        role_id=111,
        sort_order=10,
    )

    result = await repository.list_for_guild(
        123,
    )

    assert tuple(context.context_key for context in result) == (
        "ai-content",
        "notifications",
    )


async def test_context_definitions_are_isolated_by_guild(
    tmp_path: Path,
) -> None:
    """Never expose another guild's context configuration."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_context(
        database,
        guild_id=123,
        context_key="first",
        capability_key="first_capability",
        role_id=111,
    )

    await _insert_context(
        database,
        guild_id=456,
        context_key="second",
        capability_key="second_capability",
        role_id=222,
    )

    first = await repository.list_for_guild(
        123,
    )

    second = await repository.list_for_guild(
        456,
    )

    assert tuple(context.context_key for context in first) == ("first",)

    assert tuple(context.context_key for context in second) == ("second",)


async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while reading missing context configuration."""

    database_path = tmp_path / "claviger.db"

    repository = ContextDefinitionRepository(
        DatabaseConnection(
            database_path,
        )
    )

    with pytest.raises(
        DatabaseMissingError,
    ):
        await repository.get(
            guild_id=123,
            context_key="ai-content",
        )

    assert database_path.exists() is False
