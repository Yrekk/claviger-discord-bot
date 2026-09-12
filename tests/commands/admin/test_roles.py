from unittest.mock import AsyncMock, Mock

import pytest

from claviger.policies.guild_policy import GuildPolicy
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

    administrator = create_role(
        name="Administrator",
        position=100,
    )

    claviger = create_role(
        name="Claviger",
        position=50,
    )

    adult = create_role(
        name="Adult - 18+",
        position=45,
    )

    member = create_role(
        name="Member",
        position=40,
    )

    interest = create_role(
        name="interest-ai",
        position=35,
    )

    access = create_role(
        name="access-ia-casino",
        position=30,
    )

    unmanaged = create_role(
        name="Archives",
        position=20,
    )

    service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=claviger,
            trusted_roles=[
                administrator,
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

    policy_resolver.resolve.return_value = GuildPolicy(
        member_role_name="Member",
        adult_role_name="Adult - 18+",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        salutations_channel_name="welcome",
        adult_access_channel_name="adult-access",
        role_management_enabled=True,
        adult_access_enabled=True,
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
    assert "Administrator" in message

    assert "**Policy effective**" in message
    assert "Gestion des rôles : activée" in message
    assert "Accès adulte : activé" in message

    assert "**Rôle membre (1)**" in message
    assert "Member" in message

    assert "**Intérêts membre (1)**" in message
    assert "interest-ai" in message

    assert "**Rôle adulte (1)**" in message
    assert "Adult - 18+" in message

    assert "**Accès adultes — Paires (0)**" in message
    assert "**Accès adultes — Solo (0)**" in message

    assert "**Accès adultes — IA uniquement (1)**" in message
    assert "- access-ia-casino" in message

    assert "**Accès adultes — No-IA sans paire (0)**" in message
    assert "**Accès adultes non manipulables (0)**" in message

    assert "**Clés d'accès adultes invalides (0)**" in message
    assert "**Clés d'accès adultes dupliquées (0)**" in message

    assert "**Autres rôles sous Claviger (1)**" in message
    assert "Archives" in message

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


@pytest.mark.asyncio
async def test_role_scan_displays_adult_access_semantics() -> None:
    """Display every supported adult-access semantic shape."""

    service = Mock(
        spec=RoleDiscoveryService,
    )

    bot_role = create_role(
        name="Bot",
        position=50,
    )

    pair_no_ai = create_role(
        name="access-no-ia-paired",
        position=40,
    )

    pair_ai = create_role(
        name="access-ia-paired",
        position=39,
    )

    solo = create_role(
        name="access-solo",
        position=38,
    )

    ai_only = create_role(
        name="access-ia-ai-only",
        position=37,
    )

    no_ai_only = create_role(
        name="access-no-ia-incomplete",
        position=36,
    )

    unmanageable = create_role(
        name="access-unmanageable",
        position=60,
    )

    service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=bot_role,
            trusted_roles=[],
            manageable_roles=[
                pair_no_ai,
                pair_ai,
                solo,
                ai_only,
                no_ai_only,
            ],
            unmanageable_roles=[
                unmanageable,
            ],
        )
    )

    interaction = create_interaction(
        guild_id=123,
    )

    (
        command,
        _,
        _,
    ) = get_scan_command(
        service,
    )

    await command.callback(
        interaction,
    )

    message = interaction.followup.send.await_args.args[0]

    assert "**Accès adultes — Paires (1)**" in message
    assert "- paired : access-no-ia-paired + access-ia-paired" in message

    assert "**Accès adultes — Solo (2)**" in message
    assert "- access-solo" in message
    assert "- access-unmanageable" in message

    assert "**Accès adultes — IA uniquement (1)**" in message
    assert "- access-ia-ai-only" in message

    assert "**Accès adultes — No-IA sans paire (1)**" in message
    assert "- access-no-ia-incomplete" in message

    assert "**Accès adultes non manipulables (1)**" in message
    assert "- access-unmanageable" in message

    assert 'Accès no-IA sans variante IA : "access-no-ia-incomplete".' in message

    assert 'Rôle d\'accès adulte non manipulable : "access-unmanageable".' in message
