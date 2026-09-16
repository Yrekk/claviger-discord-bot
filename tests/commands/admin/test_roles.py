from unittest.mock import AsyncMock, Mock

import pytest

from claviger.reporting.event import ReportSeverity
from claviger.services.roles.role_discovery import RoleDiscoveryService, RoleHierarchy

from .helpers import create_interaction, create_role, get_scan_command


@pytest.mark.asyncio
async def test_role_scan_rejects_interaction_outside_guild() -> None:
    """Reject role scans outside a Discord server."""

    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction()
    interaction.guild = None

    command, policy_resolver, report_service = get_scan_command(service)

    await command.callback(interaction)

    service.get_hierarchy.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_role_scan_rejects_non_owner() -> None:
    """Reject role scans from users who are not the guild owner."""

    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction(owner_id=42, user_id=84)

    command, policy_resolver, report_service = get_scan_command(service)

    await command.callback(interaction)

    service.get_hierarchy.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_role_scan_displays_technical_hierarchy() -> None:
    """Display only the Discord role hierarchy without workflow semantics."""

    service = Mock(spec=RoleDiscoveryService)

    administrator = create_role(
        name="Administrator",
        position=100,
        role_id=1000,
    )
    application = create_role(
        name="Experimentum",
        position=50,
        role_id=500,
    )
    primary_candidate = create_role(
        name="Member",
        position=40,
        role_id=400,
    )
    catalog_like_role = create_role(
        name="interest-ai",
        position=35,
        role_id=350,
    )
    unmanageable = create_role(
        name="Managed integration",
        position=30,
        role_id=300,
    )

    service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=application,
            trusted_roles=[administrator],
            manageable_roles=[primary_candidate, catalog_like_role],
            unmanageable_roles=[unmanageable],
        )
    )

    interaction = create_interaction(guild_id=123)

    command, policy_resolver, report_service = get_scan_command(service)

    await command.callback(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    service.get_hierarchy.assert_awaited_once_with(interaction.guild)

    # Role scan is deliberately independent from the historical guild policy.
    policy_resolver.resolve.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once()
    message = interaction.followup.send.await_args.args[0]

    assert "**Rôle de l'application :** Experimentum (`500`)" in message
    assert "**Rôles de confiance (1)**" in message
    assert "- Administrator (`1000`)" in message
    assert "**Rôles techniquement manipulables (2)**" in message
    assert "- Member (`400`)" in message
    assert "- interest-ai (`350`)" in message
    assert "**Rôles non manipulables (1)**" in message
    assert "- Managed integration (`300`)" in message

    assert "Policy effective" not in message
    assert "Rôle membre" not in message
    assert "Rôle adulte" not in message
    assert "Accès adulte" not in message
    assert "Intérêts membre" not in message

    assert (
        "L'éligibilité d'un rôle pour un workflow est calculée séparément "
        "à partir de la configuration persistée."
    ) in message


@pytest.mark.asyncio
async def test_role_scan_reports_discovery_error() -> None:
    """Report hierarchy discovery failures without modifying Discord."""

    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock(
        side_effect=RuntimeError("Claviger's highest role could not be found.")
    )

    interaction = create_interaction(guild_id=123, user_id=42)

    command, policy_resolver, report_service = get_scan_command(service)

    await command.callback(interaction)

    interaction.response.defer.assert_awaited_once_with(ephemeral=True)
    policy_resolver.resolve.assert_not_awaited()

    report_service.emit.assert_awaited_once()
    event = report_service.emit.await_args.args[0]

    assert event.event_type == "roles.scan.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.guild_id == interaction.guild.id
    assert event.guild_label == interaction.guild.name
    assert event.actor_id == interaction.user.id
    assert event.actor_label == interaction.user.display_name
    assert event.details == "Claviger's highest role could not be found."

    interaction.followup.send.assert_awaited_once_with(
        (
            "Impossible d'analyser les rôles : "
            "Claviger's highest role could not be found."
        ),
        ephemeral=True,
    )
