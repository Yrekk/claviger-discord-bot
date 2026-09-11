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
        command_channel_id=1001,
        activity_forum_id=1002,
        error_forum_id=1003,
    )

    await repository.save(
        configuration,
    )

    assert (
        await repository.get(
            123,
        )
        == configuration
    )


async def test_save_updates_existing_admin_configuration(
    tmp_path: Path,
) -> None:
    """Replace the existing routing without creating duplicate guild rows."""

    repository = await _create_repository(
        tmp_path,
    )

    await repository.save(
        GuildAdminConfiguration(
            guild_id=123,
            category_id=1000,
            command_channel_id=1001,
            activity_forum_id=1002,
            error_forum_id=1003,
        )
    )

    updated = GuildAdminConfiguration(
        guild_id=123,
        category_id=2000,
        command_channel_id=2001,
        activity_forum_id=2002,
        error_forum_id=2003,
    )

    await repository.save(
        updated,
    )

    assert (
        await repository.get(
            123,
        )
        == updated
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
                command_channel_id=1001,
                activity_forum_id=1002,
                error_forum_id=1002,
            )
        )
