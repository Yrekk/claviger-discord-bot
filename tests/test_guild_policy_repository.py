from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection, DatabaseMissingError
from claviger.database.schema import DatabaseSchema
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)


async def create_repository(
    tmp_path: Path,
) -> GuildPolicyRepository:
    """Create an initialized temporary guild policy repository."""

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
async def test_get_returns_none_when_guild_has_no_configuration(
    tmp_path: Path,
) -> None:
    """Return None when the database contains no row for the guild."""

    repository = await create_repository(
        tmp_path,
    )

    overrides = await repository.get(
        123,
    )

    assert overrides is None


@pytest.mark.asyncio
async def test_save_and_get_guild_policy_overrides(
    tmp_path: Path,
) -> None:
    """Persist and reload guild-specific policy overrides."""

    repository = await create_repository(
        tmp_path,
    )

    expected = GuildPolicyOverrides(
        adult_role_name="Accès adulte",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        role_management_enabled=True,
        adult_access_enabled=False,
    )

    await repository.save(
        123,
        expected,
    )

    actual = await repository.get(
        123,
    )

    assert actual == expected


@pytest.mark.asyncio
async def test_save_supports_empty_overrides(
    tmp_path: Path,
) -> None:
    """Persist an explicit guild configuration with no overridden values."""

    repository = await create_repository(
        tmp_path,
    )

    await repository.save(
        123,
        GuildPolicyOverrides(),
    )

    actual = await repository.get(
        123,
    )

    assert actual == GuildPolicyOverrides()


@pytest.mark.asyncio
async def test_save_replaces_existing_overrides(
    tmp_path: Path,
) -> None:
    """Replace the complete override set when a guild is saved again."""

    repository = await create_repository(
        tmp_path,
    )

    await repository.save(
        123,
        GuildPolicyOverrides(
            adult_role_name="Ancien rôle",
            role_management_enabled=True,
        ),
    )

    replacement = GuildPolicyOverrides(
        member_role_name="Citoyen",
        adult_access_enabled=True,
    )

    await repository.save(
        123,
        replacement,
    )

    actual = await repository.get(
        123,
    )

    assert actual == replacement


@pytest.mark.asyncio
async def test_guild_configurations_are_isolated(
    tmp_path: Path,
) -> None:
    """Keep policy overrides isolated by Discord guild ID."""

    repository = await create_repository(
        tmp_path,
    )

    first = GuildPolicyOverrides(
        member_role_name="Membre A",
    )
    second = GuildPolicyOverrides(
        member_role_name="Membre B",
    )

    await repository.save(
        123,
        first,
    )
    await repository.save(
        456,
        second,
    )

    assert await repository.get(123) == first
    assert await repository.get(456) == second


@pytest.mark.asyncio
async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while trying to read missing configuration."""
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
