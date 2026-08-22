from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.claviger import create_claviger_group
from claviger.services.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)


def create_interaction(
    *,
    owner_id: int = 42,
    user_id: int = 42,
) -> Mock:
    """Create a mocked guild interaction for Claviger command tests."""
    interaction = Mock(spec=discord.Interaction)

    guild = Mock(spec=discord.Guild)
    guild.owner_id = owner_id

    user = Mock(spec=discord.Member)
    user.id = user_id

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    return interaction


def create_role(
    *,
    name: str,
    position: int,
) -> Mock:
    """Create a mocked Discord role for command output tests."""
    role = Mock(spec=discord.Role)

    role.name = name
    role.position = position

    return role


def get_scan_command(
    service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger roles scan command."""
    claviger_group = create_claviger_group(
        service,
    )

    roles_group = claviger_group.get_command(
        "roles",
    )

    assert roles_group is not None

    scan_command = roles_group.get_command(
        "scan",
    )

    assert scan_command is not None

    return scan_command


@pytest.mark.asyncio
async def test_role_scan_rejects_interaction_outside_guild() -> None:
    """Reject role scans outside a Discord server."""
    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction()
    interaction.guild = None

    command = get_scan_command(service)

    await command.callback(
        interaction,
    )

    service.get_hierarchy.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_role_scan_rejects_non_owner() -> None:
    """Reject role scans from users who are not the guild owner."""
    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    command = get_scan_command(service)

    await command.callback(
        interaction,
    )

    service.get_hierarchy.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_role_scan_displays_discovered_hierarchy() -> None:
    """Display the hierarchy returned by RoleDiscoveryService."""
    service = Mock(spec=RoleDiscoveryService)

    dux = create_role(
        name="Dux Inutilis",
        position=100,
    )
    claviger = create_role(
        name="Claviger",
        position=50,
    )
    member = create_role(
        name="Membre",
        position=40,
    )

    service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=claviger,
            trusted_roles=[
                dux,
            ],
            manageable_roles=[
                member,
            ],
        )
    )

    interaction = create_interaction()

    command = get_scan_command(service)

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    service.get_hierarchy.assert_awaited_once_with(
        interaction.guild,
    )

    interaction.followup.send.assert_awaited_once()

    message = interaction.followup.send.await_args.args[0]

    assert "Claviger" in message
    assert "Dux Inutilis" in message
    assert "Membre" in message
    assert "Rôles au-dessus (1)" in message
    assert "Rôles en dessous (1)" in message


@pytest.mark.asyncio
async def test_role_scan_reports_discovery_error() -> None:
    """Report hierarchy discovery failures without modifying Discord."""
    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock(
        side_effect=RuntimeError(
            "Claviger's highest role could not be found."
        )
    )

    interaction = create_interaction()

    command = get_scan_command(service)

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    interaction.followup.send.assert_awaited_once_with(
        (
            "Impossible d'analyser les rôles : "
            "Claviger's highest role could not be found."
        ),
        ephemeral=True,
    )