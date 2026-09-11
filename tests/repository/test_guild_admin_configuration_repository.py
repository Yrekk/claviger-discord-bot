from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)

pytestmark = pytest.mark.asyncio


async def _create_repository(
    tmp_path: Path,
) -> GuildAdminConfigurationRepository:
    """Create one repository backed by the current database schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    await DatabaseSchema(
        database,
    ).initialize()

    return GuildAdminConfigurationRepository(
        database,
    )


async def test_get_returns_none_when_guild_is_not_configured(
    tmp_path: Path,
) -> None:
    """Represent an unconfigured guild without inventing defaults."""

    repository = await _create_repository(
        tmp_path,
    )

    assert (
        await repository.get(
            123,
        )
        is None
    )


async def test_save_persists_bootstrap_admin_configuration(
    tmp_path: Path,
) -> None:
    """Persist the minimal administrative bootstrap configuration."""

    repository = await _create_repository(
        tmp_path,
    )

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=1000,
        activity_forum_id=1002,
        command_channel_id=None,
        error_forum_id=None,
    )

    await repository.save(
        configuration,
    )

    loaded = await repository.get(
        123,
    )

    assert loaded == configuration
    assert loaded is not None
    assert loaded.is_complete is False


async def test_save_persists_complete_admin_configuration(
    tmp_path: Path,
) -> None:
    """Persist and reload one complete administrative configuration."""

    repository = await _create_repository(
        tmp_path,
    )

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=1000,
        activity_forum_id=1002,
        command_channel_id=1001,
        error_forum_id=1003,
    )

    await repository.save(
        configuration,
    )

    loaded = await repository.get(
        123,
    )

    assert loaded == configuration
    assert loaded is not None
    assert loaded.is_complete is True


async def test_save_updates_bootstrap_to_complete_configuration(
    tmp_path: Path,
) -> None:
    """Complete an existing bootstrap configuration without duplicate rows."""

    repository = await _create_repository(
        tmp_path,
    )

    await repository.save(
        GuildAdminConfiguration(
            guild_id=123,
            category_id=1000,
            activity_forum_id=1002,
            command_channel_id=None,
            error_forum_id=None,
        )
    )

    updated = GuildAdminConfiguration(
        guild_id=123,
        category_id=1000,
        activity_forum_id=1002,
        command_channel_id=1001,
        error_forum_id=1003,
    )

    await repository.save(
        updated,
    )

    loaded = await repository.get(
        123,
    )

    assert loaded == updated
    assert loaded is not None
    assert loaded.is_complete is True


async def test_save_rejects_invalid_optional_identifier(
    tmp_path: Path,
) -> None:
    """Reject invalid optional Discord identifiers when configured."""

    repository = await _create_repository(
        tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="command_channel_id must be greater than zero when configured",
    ):
        await repository.save(
            GuildAdminConfiguration(
                guild_id=123,
                category_id=1000,
                activity_forum_id=1002,
                command_channel_id=0,
                error_forum_id=None,
            )
        )


async def test_save_rejects_same_activity_and_error_forum(
    tmp_path: Path,
) -> None:
    """Never route activity and error reporting to the same forum."""

    repository = await _create_repository(
        tmp_path,
    )

    with pytest.raises(
        ValueError,
        match="Activity and error forums must be different",
    ):
        await repository.save(
            GuildAdminConfiguration(
                guild_id=123,
                category_id=1000,
                activity_forum_id=1002,
                command_channel_id=1001,
                error_forum_id=1002,
            )
        )
