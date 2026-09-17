from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection, DatabaseMissingError
from claviger.database.schema import DatabaseSchema
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationState,
)
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_policy_repository import (
    GuildPolicyRepository,
)


async def create_repository(
    tmp_path: Path,
) -> tuple[GuildAIConfigurationRepository, DatabaseConnection]:
    """Create an initialized temporary V11 AI configuration repository."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    schema = DatabaseSchema(
        database,
    )
    await schema.initialize()

    return GuildAIConfigurationRepository(database), database


@pytest.mark.asyncio
async def test_get_returns_none_when_guild_has_no_settings_row(
    tmp_path: Path,
) -> None:
    """Distinguish a missing guild_settings row from unconfigured AI values."""

    repository, _ = await create_repository(tmp_path)

    assert await repository.get(123) is None


@pytest.mark.asyncio
async def test_save_and_get_unconfigured_ai_state(
    tmp_path: Path,
) -> None:
    """Persist an existing guild row whose AI activation is not configured yet."""

    repository, _ = await create_repository(tmp_path)
    expected = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=None,
        ai_role_id=None,
    )

    await repository.save(expected)

    actual = await repository.get(123)

    assert actual == expected
    assert actual is not None
    assert actual.state == GuildAIConfigurationState.UNCONFIGURED


@pytest.mark.asyncio
async def test_save_and_get_enabled_ai_without_role(
    tmp_path: Path,
) -> None:
    """Preserve the intermediate enabled state until a role is selected."""

    repository, _ = await create_repository(tmp_path)
    expected = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=True,
        ai_role_id=None,
    )

    await repository.save(expected)

    assert await repository.get(123) == expected


@pytest.mark.asyncio
async def test_save_and_get_enabled_ai_with_role(
    tmp_path: Path,
) -> None:
    """Persist the shared Discord role used by an AI-enabled guild."""

    repository, _ = await create_repository(tmp_path)
    expected = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=True,
        ai_role_id=999,
    )

    await repository.save(expected)

    assert await repository.get(123) == expected


@pytest.mark.asyncio
async def test_save_replaces_only_ai_configuration_values(
    tmp_path: Path,
) -> None:
    """Allow later AI choices to replace the previous persisted state."""

    repository, _ = await create_repository(tmp_path)

    await repository.save(
        GuildAIConfiguration(
            guild_id=123,
            ai_enabled=True,
            ai_role_id=999,
        )
    )

    replacement = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=False,
        ai_role_id=None,
    )
    await repository.save(replacement)

    assert await repository.get(123) == replacement


@pytest.mark.asyncio
async def test_ai_configurations_are_isolated_by_guild(
    tmp_path: Path,
) -> None:
    """Keep AI configuration independent for each Discord guild."""

    repository, _ = await create_repository(tmp_path)
    first = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=True,
        ai_role_id=111,
    )
    second = GuildAIConfiguration(
        guild_id=456,
        ai_enabled=False,
        ai_role_id=None,
    )

    await repository.save(first)
    await repository.save(second)

    assert await repository.get(123) == first
    assert await repository.get(456) == second


@pytest.mark.asyncio
async def test_ai_save_preserves_policy_columns_in_shared_settings_row(
    tmp_path: Path,
) -> None:
    """Do not overwrite policy data merely because both contracts share one table."""

    ai_repository, database = await create_repository(tmp_path)
    policy_repository = GuildPolicyRepository(database)
    policy = GuildPolicyOverrides(
        member_role_name="Membre",
        adult_access_prefix="access-",
        adult_access_enabled=True,
    )
    await policy_repository.save(123, policy)

    await ai_repository.save(
        GuildAIConfiguration(
            guild_id=123,
            ai_enabled=True,
            ai_role_id=999,
        )
    )

    assert await policy_repository.get(123) == policy


@pytest.mark.asyncio
async def test_policy_save_preserves_ai_columns_in_shared_settings_row(
    tmp_path: Path,
) -> None:
    """Keep AI data intact when the historical policy repository updates its slice."""

    ai_repository, database = await create_repository(tmp_path)
    policy_repository = GuildPolicyRepository(database)
    expected = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=True,
        ai_role_id=999,
    )
    await ai_repository.save(expected)

    await policy_repository.save(
        123,
        GuildPolicyOverrides(
            member_role_name="Citoyen",
            role_management_enabled=True,
        ),
    )

    assert await ai_repository.get(123) == expected


@pytest.mark.asyncio
async def test_get_does_not_create_missing_database(
    tmp_path: Path,
) -> None:
    """Do not create SQLite while trying to read missing AI configuration."""

    database_path = tmp_path / "claviger.db"
    repository = GuildAIConfigurationRepository(
        DatabaseConnection(database_path),
    )

    with pytest.raises(DatabaseMissingError):
        await repository.get(123)

    assert database_path.exists() is False
