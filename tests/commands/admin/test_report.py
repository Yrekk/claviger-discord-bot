from unittest.mock import AsyncMock, Mock

import pytest

from claviger.services.role_discovery import RoleDiscoveryService

from .helpers import (
    create_interaction,
    get_report_test_command,
)


@pytest.mark.asyncio
async def test_report_test_emits_structured_event() -> None:
    """Allow the guild owner to emit a reporting diagnostic event."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction(
        owner_id=42,
        user_id=42,
        guild_id=123,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_report_test_command(
        service,
    )

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    service.get_hierarchy.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "report.test"
    assert event.severity.value == "info"

    assert event.guild_id == 123
    assert event.guild_label == interaction.guild.name

    assert event.actor_id == interaction.user.id
    assert event.actor_label == interaction.user.display_name

    interaction.followup.send.assert_awaited_once_with(
        ("Rapport de test émis. Vérifie le forum administratif."),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_report_test_rejects_non_owner() -> None:
    """Prevent non-owners from running reporting diagnostics."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
        guild_id=123,
    )

    (
        command,
        policy_resolver,
        report_service,
    ) = get_report_test_command(
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
