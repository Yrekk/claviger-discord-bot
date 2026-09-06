from unittest.mock import AsyncMock, Mock

import pytest

from claviger.reporting.event import ReportSeverity
from claviger.services.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)

from .helpers import (
    create_interaction,
    create_role,
    get_scan_command,
)


@pytest.mark.asyncio
async def test_role_scan_rejects_interaction_outside_guild() -> None:
    """Reject role scans outside a Discord server."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction()
    interaction.guild = None

    (
        command,
        policy_resolver,
        report_service,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

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
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

    service.get_hierarchy.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_role_scan_displays_classified_hierarchy() -> None:
    """Display the hierarchy classified using the effective guild policy."""
    service = Mock(
        spec=RoleDiscoveryService,
    )

    dux = create_role(
        name="Dux Inutilis",
        position=100,
    )

    claviger = create_role(
        name="Claviger",
        position=50,
    )

    adult = create_role(
        name="Civis Noctis - 18+",
        position=45,
    )

    member = create_role(
        name="Membre",
        position=40,
    )

    interest = create_role(
        name="interest-ia",
        position=35,
    )

    access = create_role(
        name="access-ia-yuri",
        position=30,
    )

    unmanaged = create_role(
        name="Archivum",
        position=20,
    )

    service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=claviger,
            trusted_roles=[
                dux,
            ],
            manageable_roles=[
                adult,
                member,
                interest,
                access,
                unmanaged,
            ],
        )
    )

    interaction = create_interaction(
        guild_id=123,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    service.get_hierarchy.assert_awaited_once_with(
        interaction.guild,
    )

    policy_resolver.resolve.assert_awaited_once_with(
        interaction.guild.id,
    )

    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once()

    message = interaction.followup.send.await_args.args[0]

    assert "Claviger" in message
    assert "Dux Inutilis" in message

    assert "**Policy effective**" in message
    assert "Gestion des rôles : activée" in message
    assert "Accès adulte : activé" in message

    assert "**Rôle membre (1)**" in message
    assert "Membre" in message

    assert "**Intérêts membre (1)**" in message
    assert "interest-ia" in message

    assert "**Rôle adulte (1)**" in message
    assert "Civis Noctis - 18+" in message

    assert "**Accès adultes (1)**" in message
    assert "access-ia-yuri" in message

    assert "**Autres rôles sous Claviger (1)**" in message
    assert "Archivum" in message

    assert "**Anomalies (0)**" in message
    assert "- Aucune" in message


@pytest.mark.asyncio
async def test_role_scan_reports_discovery_error() -> None:
    """Report hierarchy discovery failures without modifying Discord."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock(
        side_effect=RuntimeError("Claviger's highest role could not be found.")
    )

    interaction = create_interaction(
        guild_id=123,
        user_id=42,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    policy_resolver.resolve.assert_not_awaited()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "roles.scan.failed"
    assert event.severity.value == "error"

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


@pytest.mark.asyncio
async def test_role_scan_reports_unexpected_error() -> None:
    """Report unexpected role discovery failures."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock(
        side_effect=ValueError("Unexpected Discord failure.")
    )

    interaction = create_interaction(
        guild_id=123,
        user_id=42,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

    policy_resolver.resolve.assert_not_awaited()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "roles.scan.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.details == "Unexpected Discord failure."

    interaction.followup.send.assert_awaited_once_with(
        "Impossible d'analyser les rôles : Unexpected Discord failure.",
        ephemeral=True,
    )
