from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.reporting.event import ReportSeverity
from claviger.services.guild_policy_bootstrap import (
    GuildAlreadyConfiguredError,
)
from claviger.services.role_discovery import RoleDiscoveryService

from .helpers import (
    create_interaction,
    get_guild_bootstrap_command,
)


@pytest.mark.asyncio
async def test_guild_bootstrap_persists_initial_configuration() -> None:
    """Bootstrap the initial persistent guild configuration."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    bootstrap_service.bootstrap.return_value = GuildPolicyOverrides(
        member_role_name="Membre",
        adult_role_name="Civis Noctis - 18+",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        salutations_channel_name="salutations",
        adult_rules_channel_name="lex-noctis",
        role_management_enabled=True,
        adult_access_enabled=True,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    bootstrap_service.bootstrap.assert_awaited_once_with(
        interaction.guild.id,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "guild.bootstrap.success"
    assert event.severity == ReportSeverity.INFO

    interaction.followup.send.assert_awaited_once_with(
        "Configuration persistante du serveur initialisée avec succès.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_guild_bootstrap_rejects_existing_configuration() -> None:
    """Never overwrite an existing persistent guild configuration."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        _,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    bootstrap_service.bootstrap.side_effect = GuildAlreadyConfiguredError(
        "Already configured."
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        "Ce serveur possède déjà une configuration persistante.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_guild_bootstrap_requires_ready_database() -> None:
    """Require a ready database before guild bootstrap."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.MISSING,
        current_version=None,
        target_version=2,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    bootstrap_service.bootstrap.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        (
            "La base de données doit être prête avant "
            "d'initialiser la configuration du serveur."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_guild_bootstrap_rejects_non_owner() -> None:
    """Prevent non-owners from bootstrapping guild configuration."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    bootstrap_service.bootstrap.assert_not_awaited()
    database_status_service.check.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_guild_bootstrap_reports_unexpected_failure() -> None:
    """Report unexpected guild bootstrap failures."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        _,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    bootstrap_service.bootstrap.side_effect = RuntimeError("Bootstrap exploded.")

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "guild.bootstrap.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.details == "Bootstrap exploded."

    interaction.followup.send.assert_awaited_once_with(
        "Échec de l'initialisation de la configuration du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_guild_bootstrap_reports_database_status_failure() -> None:
    """Report unexpected database status failures during guild bootstrap."""

    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
    ) = get_guild_bootstrap_command(
        service,
    )

    database_status_service.check.side_effect = RuntimeError(
        "Database status exploded."
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    bootstrap_service.bootstrap.assert_not_awaited()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "guild.bootstrap.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.details == "Database status exploded."

    interaction.followup.send.assert_awaited_once_with(
        "Échec de l'initialisation de la configuration du serveur.",
        ephemeral=True,
    )
