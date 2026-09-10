from pathlib import Path

import pytest

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseMissingError,
)
from claviger.database.schema import DatabaseSchema
from claviger.models.catalog_definition_model import CatalogDefinition
from claviger.models.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.repositories.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_repository(
    tmp_path: Path,
) -> tuple[
    DatabaseConnection,
    WorkflowDefinitionRepository,
]:
    """Create an initialized workflow definition repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return (
        database,
        WorkflowDefinitionRepository(
            database,
        ),
    )


async def _insert_catalog(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    catalog_key: str,
    role_prefix: str,
    sort_order: int = 0,
    enabled: bool = True,
) -> None:
    """Insert one catalog used by workflow tests."""

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_catalogs (
                guild_id,
                catalog_key,
                role_prefix,
                display_name,
                entry_name,
                sort_order,
                enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                catalog_key,
                role_prefix,
                catalog_key,
                catalog_key,
                sort_order,
                enabled,
            ),
        )

        await connection.commit()


async def _insert_workflow(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    workflow_key: str = "member",
    command_name: str = "membre",
    policy_key: str = "public",
    channel_mode: str = "restricted",
    sort_order: int = 0,
    enabled: bool = True,
) -> None:
    """Insert one workflow definition used by tests."""

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                guild_id,
                workflow_key,
                command_name,
                f"Configure {workflow_key}.",
                workflow_key.title(),
                f"{workflow_key.title()} workflow.",
                policy_key,
                channel_mode,
                sort_order,
                enabled,
            ),
        )

        await connection.commit()


async def _bind_catalog(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    workflow_key: str = "member",
    catalog_key: str,
    policy_key: str | None = None,
    sort_order: int = 0,
    enabled: bool = True,
) -> None:
    """Bind one catalog to one workflow."""

    async with database.connect() as connection:
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
            """,
            (
                guild_id,
                workflow_key,
                catalog_key,
                policy_key,
                sort_order,
                enabled,
            ),
        )

        await connection.commit()


async def _bind_channel(
    database: DatabaseConnection,
    *,
    guild_id: int = 123,
    workflow_key: str = "member",
    channel_id: int,
) -> None:
    """Bind one Discord channel ID to one workflow."""

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_workflow_channels (
                guild_id,
                workflow_key,
                channel_id
            )
            VALUES (?, ?, ?)
            """,
            (
                guild_id,
                workflow_key,
                channel_id,
            ),
        )

        await connection.commit()


async def test_get_by_command_name_returns_complete_workflow(
    tmp_path: Path,
) -> None:
    """Hydrate workflow routing, channels and bound catalogs."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_catalog(
        database,
        catalog_key="interests",
        role_prefix="interest-",
        sort_order=10,
    )

    await _insert_catalog(
        database,
        catalog_key="premium",
        role_prefix="access-premium-",
        sort_order=20,
    )

    await _insert_workflow(
        database,
    )

    await _bind_catalog(
        database,
        catalog_key="premium",
        policy_key="premium",
        sort_order=20,
    )

    await _bind_catalog(
        database,
        catalog_key="interests",
        sort_order=10,
    )

    await _bind_channel(
        database,
        channel_id=222,
    )

    await _bind_channel(
        database,
        channel_id=111,
    )

    result = await repository.get_by_command_name(
        guild_id=123,
        command_name="membre",
    )

    assert result == WorkflowDefinition(
        guild_id=123,
        workflow_key="member",
        command_name="membre",
        command_description="Configure member.",
        title="Member",
        description="Member workflow.",
        policy_key="public",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(
            111,
            222,
        ),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=CatalogDefinition(
                    guild_id=123,
                    catalog_key="interests",
                    role_prefix="interest-",
                    display_name="interests",
                    entry_name="interests",
                    description=None,
                    sort_order=10,
                    enabled=True,
                ),
                policy_key=None,
                sort_order=10,
                enabled=True,
            ),
            WorkflowCatalogBinding(
                catalog=CatalogDefinition(
                    guild_id=123,
                    catalog_key="premium",
                    role_prefix="access-premium-",
                    display_name="premium",
                    entry_name="premium",
                    description=None,
                    sort_order=20,
                    enabled=True,
                ),
                policy_key="premium",
                sort_order=20,
                enabled=True,
            ),
        ),
    )


async def test_get_returns_workflow_by_stable_key(
    tmp_path: Path,
) -> None:
    """Resolve a workflow independently from its Discord command name."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_workflow(
        database,
        workflow_key="premium-access",
        command_name="premium",
        policy_key="premium",
        channel_mode="any",
    )

    result = await repository.get(
        guild_id=123,
        workflow_key="premium-access",
    )

    assert result is not None
    assert result.workflow_key == "premium-access"
    assert result.command_name == "premium"
    assert result.policy_key == "premium"
    assert result.channel_mode == "any"


async def test_unknown_workflow_returns_none(
    tmp_path: Path,
) -> None:
    """Return None when no workflow matches the requested command."""

    _, repository = await _create_repository(
        tmp_path,
    )

    result = await repository.get_by_command_name(
        guild_id=123,
        command_name="missing",
    )

    assert result is None


async def test_list_for_guild_orders_workflows(
    tmp_path: Path,
) -> None:
    """Return workflows using their configured order."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_workflow(
        database,
        workflow_key="premium",
        command_name="premium",
        policy_key="premium",
        sort_order=20,
    )

    await _insert_workflow(
        database,
        workflow_key="member",
        command_name="membre",
        sort_order=10,
    )

    result = await repository.list_for_guild(
        123,
    )

    assert tuple(workflow.workflow_key for workflow in result) == (
        "member",
        "premium",
    )


async def test_workflows_are_isolated_by_guild(
    tmp_path: Path,
) -> None:
    """Never resolve another guild's workflow configuration."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_workflow(
        database,
        guild_id=123,
        workflow_key="first",
        command_name="configure",
    )

    await _insert_workflow(
        database,
        guild_id=456,
        workflow_key="second",
        command_name="configure",
    )

    first = await repository.get_by_command_name(
        guild_id=123,
        command_name="configure",
    )

    second = await repository.get_by_command_name(
        guild_id=456,
        command_name="configure",
    )

    assert first is not None
    assert second is not None

    assert first.workflow_key == "first"
    assert second.workflow_key == "second"


async def test_repository_preserves_disabled_configuration(
    tmp_path: Path,
) -> None:
    """Expose persisted enabled state without applying business filtering."""

    database, repository = await _create_repository(
        tmp_path,
    )

    await _insert_catalog(
        database,
        catalog_key="beta",
        role_prefix="access-beta-",
        enabled=False,
    )

    await _insert_workflow(
        database,
        workflow_key="beta",
        command_name="beta",
        policy_key="beta",
        enabled=False,
    )

    await _bind_catalog(
        database,
        workflow_key="beta",
        catalog_key="beta",
        enabled=False,
    )

    result = await repository.get(
        guild_id=123,
        workflow_key="beta",
    )

    assert result is not None
    assert result.enabled is False

    assert len(result.catalogs) == 1
    assert result.catalogs[0].enabled is False
    assert result.catalogs[0].catalog.enabled is False


async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while reading missing workflow configuration."""

    database_path = tmp_path / "claviger.db"

    repository = WorkflowDefinitionRepository(
        DatabaseConnection(
            database_path,
        )
    )

    with pytest.raises(
        DatabaseMissingError,
    ):
        await repository.get_by_command_name(
            guild_id=123,
            command_name="membre",
        )

    assert database_path.exists() is False
