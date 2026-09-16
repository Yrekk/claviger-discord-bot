from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from claviger.commands.admin.admin_command_group import GuildAdminCommandGroup
from claviger.models.admin.admin_configuration_inspection_model import (
    AdminConfigurationInspectionResult,
)
from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminStructureDiscoveryResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


async def _dummy_command(
    interaction: discord.Interaction,
) -> None:
    """Provide a no-op command callback for routing tests."""


def _ready_inspection() -> AdminConfigurationInspectionResult:
    """Create one healthy persisted ADMIN routing inspection."""

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    return AdminConfigurationInspectionResult(
        guild_id=123,
        configuration=configuration,
        discovery=AdminStructureDiscoveryResult(
            categories=(),
        ),
        reconciliation=AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category=None,
        ),
    )


def _unready_inspection() -> AdminConfigurationInspectionResult:
    """Create one persisted ADMIN routing inspection requiring repair."""

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    return AdminConfigurationInspectionResult(
        guild_id=123,
        configuration=configuration,
        discovery=AdminStructureDiscoveryResult(
            categories=(),
        ),
        reconciliation=AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.CREATE,
            category=None,
            issues=("Configured ADMIN category disappeared.",),
        ),
    )


def _create_interaction(
    *,
    channel_id: int,
    command: app_commands.Command,
) -> Mock:
    """Create one mocked Discord interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    interaction.guild = Mock(
        spec=discord.Guild,
    )
    interaction.guild.id = 123

    interaction.channel_id = channel_id
    interaction.command = command

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


def _create_admin_group(
    *,
    inspection: AdminConfigurationInspectionResult | None,
) -> tuple[
    GuildAdminCommandGroup,
    app_commands.Command,
    app_commands.Command,
    app_commands.Command,
    app_commands.Command,
    AsyncMock | None,
]:
    """Create one ADMIN group containing normal and recovery commands."""

    routing_inspector = (
        AsyncMock(
            return_value=inspection,
        )
        if inspection is not None
        else None
    )

    group = GuildAdminCommandGroup(
        name="experimentum",
        description="Administration.",
        routing_inspector=routing_inspector,
    )

    report_group = app_commands.Group(
        name="report",
        description="Reporting.",
    )

    report_command = app_commands.Command(
        name="test",
        description="Test.",
        callback=_dummy_command,
    )

    report_group.add_command(
        report_command,
    )

    database_group = app_commands.Group(
        name="database",
        description="Database.",
    )

    database_command = app_commands.Command(
        name="status",
        description="Status.",
        callback=_dummy_command,
    )

    database_group.add_command(
        database_command,
    )

    restart_command = app_commands.Command(
        name="restart",
        description="Restart.",
        callback=_dummy_command,
    )

    config_server_command = app_commands.Command(
        name="config-server",
        description="Configuration.",
        callback=_dummy_command,
    )

    group.add_command(
        report_group,
    )

    group.add_command(
        database_group,
    )

    group.add_command(
        restart_command,
    )

    group.add_command(
        config_server_command,
    )

    return (
        group,
        report_command,
        database_command,
        restart_command,
        config_server_command,
        routing_inspector,
    )


@pytest.mark.asyncio
async def test_nested_admin_command_accepts_configured_channel() -> None:
    """Allow nested ADMIN commands in the live configured ADMIN channel."""

    _, report_command, _, _, _, routing_inspector = _create_admin_group(
        inspection=_ready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=200,
        command=report_command,
    )

    assert await report_command._check_can_run(interaction) is True

    interaction.response.send_message.assert_not_awaited()
    assert routing_inspector is not None
    routing_inspector.assert_awaited_once_with(
        interaction.guild,
    )


@pytest.mark.asyncio
async def test_nested_admin_command_rejects_other_channel() -> None:
    """Reject nested ADMIN commands outside the live configured ADMIN channel."""

    _, report_command, _, _, _, _ = _create_admin_group(
        inspection=_ready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=report_command,
    )

    assert await report_command._check_can_run(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande administrative doit être utilisée dans <#200>.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_command_is_restricted_when_admin_routing_is_healthy() -> None:
    """Treat database maintenance as normal ADMIN once ADMIN routing is healthy."""

    _, _, database_command, _, _, _ = _create_admin_group(
        inspection=_ready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=database_command,
    )

    assert await database_command._check_can_run(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande administrative doit être utilisée dans <#200>.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_restart_is_restricted_when_admin_routing_is_healthy() -> None:
    """Treat restart as normal ADMIN once ADMIN routing is healthy."""

    group, _, _, restart_command, _, _ = _create_admin_group(
        inspection=_ready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=restart_command,
    )

    assert await group.interaction_check(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande administrative doit être utilisée dans <#200>.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_config_server_is_restricted_when_admin_routing_is_healthy() -> None:
    """Treat config-server as normal ADMIN once ADMIN routing is healthy."""

    group, _, _, _, config_server_command, _ = _create_admin_group(
        inspection=_ready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=config_server_command,
    )

    assert await group.interaction_check(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande administrative doit être utilisée dans <#200>.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_command_becomes_recovery_when_admin_routing_drifted() -> None:
    """Keep database recovery reachable when persisted ADMIN no longer matches Discord."""

    _, _, database_command, _, _, _ = _create_admin_group(
        inspection=_unready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=database_command,
    )

    assert await database_command._check_can_run(interaction) is True

    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_config_server_becomes_recovery_when_admin_routing_drifted() -> None:
    """Keep config-server reachable when ADMIN Discord resources disappeared."""

    group, _, _, _, config_server_command, _ = _create_admin_group(
        inspection=_unready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=config_server_command,
    )

    assert await group.interaction_check(interaction) is True


@pytest.mark.asyncio
async def test_normal_admin_command_fails_closed_when_admin_routing_drifted() -> None:
    """Block non-recovery ADMIN commands while ADMIN routing requires repair."""

    _, report_command, _, _, _, _ = _create_admin_group(
        inspection=_unready_inspection(),
    )

    interaction = _create_interaction(
        channel_id=999,
        command=report_command,
    )

    assert await report_command._check_can_run(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        (
            "La configuration ADMIN de ce serveur est absente, incomplète "
            "ou ne correspond plus à Discord. "
            "Utilise `/experimentum config-server` pour la réparer."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_recovery_commands_remain_available_without_routing_inspector() -> None:
    """Keep recovery reachable while the application database is not operational."""

    group, _, database_command, restart_command, config_server_command, _ = (
        _create_admin_group(
            inspection=None,
        )
    )

    for command in (
        database_command,
        restart_command,
        config_server_command,
    ):
        interaction = _create_interaction(
            channel_id=999,
            command=command,
        )

        if command is database_command:
            assert await command._check_can_run(interaction) is True
        else:
            assert await group.interaction_check(interaction) is True

        interaction.response.send_message.assert_not_awaited()
