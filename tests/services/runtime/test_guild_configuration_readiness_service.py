from unittest.mock import AsyncMock, Mock

import pytest

from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.models.runtime.guild_configuration_readiness_model import (
    GuildConfigurationReadinessState,
)
from claviger.repositories.admin.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
from claviger.services.runtime.guild_configuration_readiness_service import (
    GuildConfigurationReadinessService,
)


def _create_repository() -> Mock:
    """Create a mocked ADMIN configuration repository.

    Returns:
        Mock:
            Repository mock whose asynchronous ``get`` operation can be
            configured independently by each test.
    """

    repository = Mock(
        spec=GuildAdminConfigurationRepository,
    )

    repository.get = AsyncMock()

    return repository


def _create_complete_configuration(
    *,
    guild_id: int = 123,
) -> GuildAdminConfiguration:
    """Create a complete persisted ADMIN configuration.

    Args:
        guild_id:
            Discord guild identifier stored in the configuration.

    Returns:
        GuildAdminConfiguration:
            Complete configuration containing every required ADMIN
            destination.
    """

    return GuildAdminConfiguration(
        guild_id=guild_id,
        category_id=1000,
        command_channel_id=1001,
        activity_forum_id=1002,
        error_forum_id=1003,
    )


@pytest.mark.asyncio
async def test_readiness_rejects_invalid_guild_id() -> None:
    """Reject invalid guild identifiers before touching persistence."""

    repository = _create_repository()

    service = GuildConfigurationReadinessService(
        repository,
    )

    with pytest.raises(
        ValueError,
        match="Discord guild ID must be greater than zero",
    ):
        await service.inspect(
            0,
        )

    repository.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_readiness_reports_missing_admin_configuration() -> None:
    """Treat a new guild without persisted ADMIN routing as not ready."""

    repository = _create_repository()

    repository.get.return_value = None

    service = GuildConfigurationReadinessService(
        repository,
    )

    result = await service.inspect(
        123,
    )

    assert result.guild_id == 123
    assert result.state == (
        GuildConfigurationReadinessState.ADMIN_CONFIGURATION_MISSING
    )
    assert result.configuration is None
    assert result.is_ready is False

    repository.get.assert_awaited_once_with(
        123,
    )


@pytest.mark.asyncio
async def test_readiness_reports_incomplete_admin_configuration() -> None:
    """Keep partially configured guilds unavailable to normal workflows."""

    repository = _create_repository()

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=1000,
        command_channel_id=None,
        activity_forum_id=1002,
        error_forum_id=None,
    )

    repository.get.return_value = configuration

    service = GuildConfigurationReadinessService(
        repository,
    )

    result = await service.inspect(
        123,
    )

    assert result.guild_id == 123
    assert result.state == (
        GuildConfigurationReadinessState.ADMIN_CONFIGURATION_INCOMPLETE
    )
    assert result.configuration == configuration
    assert result.is_ready is False

    repository.get.assert_awaited_once_with(
        123,
    )


@pytest.mark.asyncio
async def test_readiness_reports_complete_admin_configuration() -> None:
    """Allow normal runtime features for a completely configured guild."""

    repository = _create_repository()

    configuration = _create_complete_configuration()

    repository.get.return_value = configuration

    service = GuildConfigurationReadinessService(
        repository,
    )

    result = await service.inspect(
        123,
    )

    assert result.guild_id == 123
    assert result.state == GuildConfigurationReadinessState.READY
    assert result.configuration == configuration
    assert result.is_ready is True

    repository.get.assert_awaited_once_with(
        123,
    )
