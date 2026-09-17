from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection, DatabaseMissingError
from claviger.database.schema import DatabaseSchema
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.repositories.runtime.guild_policy_repository import (
    GuildPolicyPersistenceRetiredError,
    GuildPolicyRepository,
)


async def create_repository(
    tmp_path: Path,
) -> GuildPolicyRepository:
    """Create an initialized temporary compatibility repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return GuildPolicyRepository(
        database,
    )


@pytest.mark.asyncio
async def test_get_returns_no_sqlite_overrides_after_v11(
    tmp_path: Path,
) -> None:
    """V11 uses code snapshots instead of persisted V1 policy overrides."""

    repository = await create_repository(
        tmp_path,
    )

    assert await repository.get(123) is None


@pytest.mark.asyncio
async def test_save_rejects_retired_policy_persistence(
    tmp_path: Path,
) -> None:
    """Do not silently recreate the V1 guild-settings contract."""

    repository = await create_repository(
        tmp_path,
    )

    with pytest.raises(
        GuildPolicyPersistenceRetiredError,
        match="retired by schema V11",
    ):
        await repository.save(
            123,
            GuildPolicyOverrides(
                member_role_name="Membre",
            ),
        )


@pytest.mark.asyncio
async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while checking retired compatibility state."""

    database_path = tmp_path / "claviger.db"

    database = DatabaseConnection(
        database_path,
    )

    repository = GuildPolicyRepository(
        database,
    )

    with pytest.raises(DatabaseMissingError):
        await repository.get(
            123,
        )

    assert database_path.exists() is False


@pytest.mark.asyncio
async def test_save_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Reject obsolete writes without creating an empty SQLite file."""

    database_path = tmp_path / "claviger.db"
    repository = GuildPolicyRepository(
        DatabaseConnection(database_path),
    )

    with pytest.raises(DatabaseMissingError):
        await repository.save(
            123,
            GuildPolicyOverrides(),
        )

    assert database_path.exists() is False
