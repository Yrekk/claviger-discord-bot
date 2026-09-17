from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
)
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationAfterRoleCreationError,
    GuildAIConfigurationCoordinatorService,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationService,
)
from claviger.services.runtime.guild_ai_role_provisioning_service import (
    GuildAIRoleProvisioningService,
)


def _inspection(
    state: GuildAIConfigurationInspectionState,
) -> GuildAIConfigurationInspection:
    """Create one deterministic guild AI inspection result."""

    return GuildAIConfigurationInspection(
        guild_id=123,
        state=state,
        configuration=GuildAIConfiguration(
            guild_id=123,
            ai_enabled=(state != GuildAIConfigurationInspectionState.DISABLED),
            ai_role_id=(999 if state == GuildAIConfigurationInspectionState.READY else None),
        ),
    )


def _coordinator() -> tuple[
    GuildAIConfigurationCoordinatorService,
    Mock,
    Mock,
]:
    """Create the coordinator with mocked lower-level application services."""

    configuration_service = Mock(spec=GuildAIConfigurationService)
    configuration_service.inspect = AsyncMock()
    configuration_service.enable = AsyncMock()
    configuration_service.disable = AsyncMock()
    configuration_service.assign_role = AsyncMock()

    provisioning_service = Mock(spec=GuildAIRoleProvisioningService)
    provisioning_service.create_role = AsyncMock()

    coordinator = GuildAIConfigurationCoordinatorService(
        configuration_service=configuration_service,
        provisioning_service=provisioning_service,
    )

    return coordinator, configuration_service, provisioning_service


def _guild() -> Mock:
    """Create one deterministic Discord guild identity."""

    guild = Mock(spec=discord.Guild)
    guild.id = 123
    return guild


@pytest.mark.asyncio
async def test_enable_reinspects_preserved_role_after_persistence() -> None:
    """Revalidate a dormant role immediately after guild AI becomes enabled."""

    coordinator, configuration_service, _ = _coordinator()
    guild = _guild()
    ready = _inspection(GuildAIConfigurationInspectionState.READY)
    configuration_service.inspect.return_value = ready

    result = await coordinator.enable(guild)

    configuration_service.enable.assert_awaited_once_with(123)
    configuration_service.inspect.assert_awaited_once_with(guild)
    assert result is ready


@pytest.mark.asyncio
async def test_disable_reinspects_without_touching_role_provisioning() -> None:
    """Treat an explicit opt-out as workflow-ready without provisioning a role."""

    coordinator, configuration_service, provisioning_service = _coordinator()
    guild = _guild()
    disabled = _inspection(GuildAIConfigurationInspectionState.DISABLED)
    configuration_service.inspect.return_value = disabled

    result = await coordinator.disable(guild)

    configuration_service.disable.assert_awaited_once_with(123)
    configuration_service.inspect.assert_awaited_once_with(guild)
    provisioning_service.create_role.assert_not_awaited()
    assert result is disabled


@pytest.mark.asyncio
async def test_assign_role_delegates_validation_before_reinspection() -> None:
    """Keep existing-role safety inside the authoritative configuration service."""

    coordinator, configuration_service, _ = _coordinator()
    guild = _guild()
    ready = _inspection(GuildAIConfigurationInspectionState.READY)
    configuration_service.inspect.return_value = ready

    result = await coordinator.assign_role(
        guild,
        999,
    )

    configuration_service.assign_role.assert_awaited_once_with(
        guild,
        999,
    )
    configuration_service.inspect.assert_awaited_once_with(guild)
    assert result is ready


@pytest.mark.asyncio
async def test_create_and_assign_role_sequences_discord_then_persistence() -> None:
    """Create one role, persist its ID and expose final live readiness."""

    coordinator, configuration_service, provisioning_service = _coordinator()
    guild = _guild()
    role = Mock(spec=discord.Role)
    role.id = 999
    provisioning_service.create_role.return_value = role
    ready = _inspection(GuildAIConfigurationInspectionState.READY)
    configuration_service.inspect.return_value = ready

    result = await coordinator.create_and_assign_role(
        guild,
        "Accès IA",
    )

    provisioning_service.create_role.assert_awaited_once_with(
        guild,
        "Accès IA",
    )
    configuration_service.assign_role.assert_awaited_once_with(
        guild,
        999,
    )
    configuration_service.inspect.assert_awaited_once_with(guild)
    assert result is ready


@pytest.mark.asyncio
async def test_create_and_assign_role_reports_partial_discord_mutation() -> None:
    """Preserve the created role identity when SQLite association fails afterward."""

    coordinator, configuration_service, provisioning_service = _coordinator()
    guild = _guild()
    role = Mock(spec=discord.Role)
    role.id = 999
    provisioning_service.create_role.return_value = role
    configuration_service.assign_role.side_effect = RuntimeError("database unavailable")

    with pytest.raises(GuildAIConfigurationAfterRoleCreationError) as exc_info:
        await coordinator.create_and_assign_role(
            guild,
            "Accès IA",
        )

    assert exc_info.value.role_id == 999
    configuration_service.inspect.assert_not_awaited()
