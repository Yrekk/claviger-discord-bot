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


@pytest.mark.asyncio
async def test_config_scan_remains_available_when_admin_is_drifted() -> None:
    inspection = AdminConfigurationInspectionResult(
        guild_id=123,
        configuration=None,
        discovery=AdminStructureDiscoveryResult(
            categories=(),
        ),
        reconciliation=AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.CREATE,
            category=None,
        ),
    )

    root = GuildAdminCommandGroup(
        name="experimentum",
        description="Admin",
        routing_inspector=AsyncMock(return_value=inspection),
    )

    config_group = app_commands.Group(
        name="config",
        description="Config",
    )

    @config_group.command(
        name="scan",
        description="Scan",
    )
    async def scan(interaction: discord.Interaction) -> None:
        pass

    root.add_command(
        config_group,
    )

    command = config_group.get_command("scan")
    assert command is not None

    interaction = Mock(spec=discord.Interaction)
    guild = Mock(spec=discord.Guild)
    guild.id = 123

    interaction.guild = guild
    interaction.channel_id = 999
    interaction.command = command
    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    assert await command._check_can_run(interaction) is True
    interaction.response.send_message.assert_not_awaited()
