from unittest.mock import AsyncMock, MagicMock, Mock

import discord
import pytest

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspectionState,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationService,
    GuildAINotEnabledError,
    GuildAIRoleValidationError,
)


def make_repository(
    configuration: GuildAIConfiguration | None,
) -> Mock:
    """Create an async repository double returning one configured state."""

    repository = Mock(spec=GuildAIConfigurationRepository)
    repository.get = AsyncMock(return_value=configuration)
    repository.save = AsyncMock()
    return repository


def make_role(
    *,
    role_id: int = 999,
    name: str = "Accès IA",
    managed: bool = False,
    is_default: bool = False,
    below_bot: bool = True,
) -> MagicMock:
    """Create a Discord role double with controllable manageability."""

    role = MagicMock(spec=discord.Role)
    role.id = role_id
    role.name = name
    role.managed = managed
    role.is_default.return_value = is_default
    role.__lt__.return_value = below_bot
    return role


def make_guild(
    *,
    role: discord.Role | None = None,
    bot_member_available: bool = True,
) -> Mock:
    """Create a guild double exposing one optional role and bot member."""

    guild = Mock(spec=discord.Guild)
    guild.id = 123
    guild.get_role = Mock(return_value=role)

    if bot_member_available:
        bot_member = Mock(spec=discord.Member)
        bot_member.top_role = MagicMock(spec=discord.Role)
        guild.me = bot_member
    else:
        guild.me = None

    return guild


@pytest.mark.asyncio
async def test_inspect_reports_missing_settings_row() -> None:
    repository = make_repository(None)
    service = GuildAIConfigurationService(repository)

    inspection = await service.inspect(make_guild())

    assert inspection.state == GuildAIConfigurationInspectionState.MISSING
    assert inspection.configuration is None
    assert inspection.is_ready_for_workflows is False


@pytest.mark.asyncio
async def test_inspect_reports_unconfigured_ai_choice() -> None:
    configuration = GuildAIConfiguration(123, None, None)
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild())

    assert inspection.state == GuildAIConfigurationInspectionState.UNCONFIGURED
    assert inspection.configuration == configuration


@pytest.mark.asyncio
async def test_inspect_treats_disabled_ai_as_workflow_ready() -> None:
    configuration = GuildAIConfiguration(123, False, 999)
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild())

    assert inspection.state == GuildAIConfigurationInspectionState.DISABLED
    assert inspection.is_ready_for_workflows is True


@pytest.mark.asyncio
async def test_inspect_reports_enabled_ai_without_role() -> None:
    configuration = GuildAIConfiguration(123, True, None)
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild())

    assert inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_MISSING


@pytest.mark.asyncio
async def test_inspect_reports_deleted_configured_role() -> None:
    configuration = GuildAIConfiguration(123, True, 999)
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild(role=None))

    assert inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND


@pytest.mark.asyncio
async def test_inspect_fails_closed_when_bot_member_is_unavailable() -> None:
    configuration = GuildAIConfiguration(123, True, 999)
    role = make_role()
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(
        make_guild(role=role, bot_member_available=False)
    )

    assert inspection.state == GuildAIConfigurationInspectionState.BOT_MEMBER_UNAVAILABLE
    assert inspection.role_name == "Accès IA"
    assert inspection.is_ready_for_workflows is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role",
    (
        make_role(managed=True),
        make_role(is_default=True),
        make_role(below_bot=False),
    ),
)
async def test_inspect_rejects_unusable_configured_role(role: discord.Role) -> None:
    configuration = GuildAIConfiguration(123, True, 999)
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild(role=role))

    assert inspection.state == GuildAIConfigurationInspectionState.ENABLED_ROLE_UNUSABLE
    assert inspection.is_ready_for_workflows is False


@pytest.mark.asyncio
async def test_inspect_reports_ready_for_valid_enabled_role() -> None:
    configuration = GuildAIConfiguration(123, True, 999)
    role = make_role()
    service = GuildAIConfigurationService(make_repository(configuration))

    inspection = await service.inspect(make_guild(role=role))

    assert inspection.state == GuildAIConfigurationInspectionState.READY
    assert inspection.role_name == "Accès IA"
    assert inspection.is_ready_for_workflows is True


@pytest.mark.asyncio
async def test_enable_creates_partial_enabled_configuration() -> None:
    repository = make_repository(None)
    service = GuildAIConfigurationService(repository)

    configuration = await service.enable(123)

    assert configuration == GuildAIConfiguration(123, True, None)
    repository.save.assert_awaited_once_with(configuration)


@pytest.mark.asyncio
async def test_enable_preserves_existing_role_identifier() -> None:
    repository = make_repository(GuildAIConfiguration(123, False, 999))
    service = GuildAIConfigurationService(repository)

    configuration = await service.enable(123)

    assert configuration == GuildAIConfiguration(123, True, 999)
    repository.save.assert_awaited_once_with(configuration)


@pytest.mark.asyncio
async def test_disable_preserves_existing_role_identifier() -> None:
    repository = make_repository(GuildAIConfiguration(123, True, 999))
    service = GuildAIConfigurationService(repository)

    configuration = await service.disable(123)

    assert configuration == GuildAIConfiguration(123, False, 999)
    repository.save.assert_awaited_once_with(configuration)


@pytest.mark.asyncio
async def test_assign_role_requires_explicit_ai_enablement() -> None:
    repository = make_repository(GuildAIConfiguration(123, None, None))
    service = GuildAIConfigurationService(repository)

    with pytest.raises(GuildAINotEnabledError):
        await service.assign_role(make_guild(role=make_role()), 999)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_role_rejects_missing_role() -> None:
    repository = make_repository(GuildAIConfiguration(123, True, None))
    service = GuildAIConfigurationService(repository)

    with pytest.raises(GuildAIRoleValidationError):
        await service.assign_role(make_guild(role=None), 999)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_role_rejects_unmanageable_role() -> None:
    repository = make_repository(GuildAIConfiguration(123, True, None))
    service = GuildAIConfigurationService(repository)

    with pytest.raises(GuildAIRoleValidationError):
        await service.assign_role(make_guild(role=make_role(managed=True)), 999)

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_assign_role_persists_valid_role() -> None:
    repository = make_repository(GuildAIConfiguration(123, True, None))
    service = GuildAIConfigurationService(repository)

    configuration = await service.assign_role(make_guild(role=make_role()), 999)

    assert configuration == GuildAIConfiguration(123, True, 999)
    repository.save.assert_awaited_once_with(configuration)
