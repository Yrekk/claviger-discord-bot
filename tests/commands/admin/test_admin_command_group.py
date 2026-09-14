from unittest.mock import AsyncMock, Mock

import discord
import pytest
from discord import app_commands

from claviger.commands.admin_command_group import GuildAdminCommandGroup


async def _dummy_command(
    interaction: discord.Interaction,
) -> None:
    """Provide a no-op command callback for routing tests."""


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

    interaction.channel_id = channel_id
    interaction.command = command

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


def _create_admin_group(
    *,
    command_channel_id: int | None = 200,
) -> tuple[
    GuildAdminCommandGroup,
    app_commands.Command,
    app_commands.Command,
    app_commands.Command,
    app_commands.Command,
]:
    """Create one ADMIN group containing normal and recovery commands."""

    group = GuildAdminCommandGroup(
        name="experimentum",
        description="Administration.",
        command_channel_id=command_channel_id,
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
    )


@pytest.mark.asyncio
async def test_normal_admin_command_accepts_configured_channel() -> None:
    """Allow normal ADMIN commands in the configured channel."""

    group, report_command, _, _, _ = _create_admin_group()

    interaction = _create_interaction(
        channel_id=200,
        command=report_command,
    )

    assert await group.interaction_check(interaction) is True

    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_normal_admin_command_rejects_other_channel() -> None:
    """Reject normal ADMIN commands outside the configured channel."""

    group, report_command, _, _, _ = _create_admin_group()

    interaction = _create_interaction(
        channel_id=999,
        command=report_command,
    )

    assert await group.interaction_check(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande administrative doit être utilisée dans <#200>.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_command_remains_available_outside_admin_channel() -> None:
    """Keep database recovery commands available outside ADMIN routing."""

    group, _, database_command, _, _ = _create_admin_group()

    interaction = _create_interaction(
        channel_id=999,
        command=database_command,
    )

    assert await group.interaction_check(interaction) is True


@pytest.mark.asyncio
async def test_restart_remains_available_outside_admin_channel() -> None:
    """Keep restart available as a recovery command."""

    group, _, _, restart_command, _ = _create_admin_group()

    interaction = _create_interaction(
        channel_id=999,
        command=restart_command,
    )

    assert await group.interaction_check(interaction) is True


@pytest.mark.asyncio
async def test_config_server_remains_available_outside_admin_channel() -> None:
    """Keep config-server available as a recovery command."""

    group, _, _, _, config_server_command = _create_admin_group()

    interaction = _create_interaction(
        channel_id=999,
        command=config_server_command,
    )

    assert await group.interaction_check(interaction) is True


@pytest.mark.asyncio
async def test_normal_admin_command_fails_closed_without_channel() -> None:
    """Reject normal ADMIN commands when ADMIN routing is incomplete."""

    group, report_command, _, _, _ = _create_admin_group(
        command_channel_id=None,
    )

    interaction = _create_interaction(
        channel_id=999,
        command=report_command,
    )

    assert await group.interaction_check(interaction) is False

    interaction.response.send_message.assert_awaited_once_with(
        (
            "La configuration ADMIN de ce serveur ne définit aucun "
            "salon de commandes. "
            "Utilise `/experimentum config-server`."
        ),
        ephemeral=True,
    )
