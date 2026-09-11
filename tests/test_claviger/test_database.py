from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.reporting.event import ReportSeverity
from claviger.services.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.role_discovery import RoleDiscoveryService

from .helpers import (
    create_interaction,
    create_test_group,
    get_database_initialize_command,
    get_database_migrate_command,
    get_database_status_command,
)


@pytest.mark.asyncio
async def test_database_status_displays_current_state() -> None:
    """Display the current database state without modifying it."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_status_service,
        report_service,
    ) = get_database_status_command(
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

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    database_status_service.check.assert_awaited_once()
    report_service.emit.assert_not_awaited()

    message = interaction.followup.send.await_args.args[0]

    assert "État : **Absente**" in message
    assert "Version actuelle : `N/A`" in message
    assert "Version attendue : `2`" in message
    assert "Initialiser manuellement" in message


@pytest.mark.asyncio
async def test_database_status_rejects_non_owner() -> None:
    """Prevent non-owners from inspecting database administration."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_status_service,
        report_service,
    ) = get_database_status_command(
        service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_status_reports_unexpected_failure() -> None:
    """Report unexpected database diagnostic failures."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_status_service,
        report_service,
    ) = get_database_status_command(
        service,
    )

    database_status_service.check.side_effect = RuntimeError(
        "Unexpected diagnostic failure."
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    database_status_service.check.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "database.status.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.details == "Unexpected diagnostic failure."

    assert event.guild_id == interaction.guild.id
    assert event.guild_label == interaction.guild.name

    assert event.actor_id == interaction.user.id
    assert event.actor_label == interaction.user.display_name

    interaction.followup.send.assert_awaited_once_with(
        "Impossible de déterminer l'état de la base de données.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_initialize_creates_missing_database() -> None:
    """Initialize a missing database and verify its final state."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_initialize_command(
        service,
    )

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MISSING,
            current_version=None,
            target_version=2,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        ),
    ]

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.initialize.assert_awaited_once()

    assert database_status_service.check.await_count == 2

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "database.initialize.success"
    assert event.severity == ReportSeverity.INFO

    interaction.followup.send.assert_awaited_once_with(
        (
            "Base de données initialisée et liée à cette application. "
            "Version du schéma : `2`."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_initialize_rejects_ready_database() -> None:
    """Do not initialize an already ready database."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_initialize_command(
        service,
    )

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.READY,
        current_version=2,
        target_version=2,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.initialize.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        (
            "La base de données est déjà initialisée. "
            "Utilise `/claviger database bind` "
            "si son application propriétaire doit être vérifiée."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_initialize_rejects_non_owner() -> None:
    """Prevent non-owners from initializing the database."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_initialize_command(
        service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    database_schema.initialize.assert_not_awaited()
    database_status_service.check.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_initialize_reports_failure() -> None:
    """Report database initialization failures."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_initialize_command(
        service,
    )

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.MISSING,
        current_version=None,
        target_version=2,
    )

    database_schema.initialize.side_effect = RuntimeError("Initialization exploded.")

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "database.initialize.failed"
    assert event.severity == ReportSeverity.ERROR
    assert event.details == "Initialization exploded."

    interaction.followup.send.assert_awaited_once_with(
        "Échec de l'initialisation de la base de données.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_migrate_upgrades_outdated_database() -> None:
    """Migrate an outdated database and verify its final state."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_migrate_command(
        service,
    )

    database_status_service.check.side_effect = [
        DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=1,
            target_version=2,
        ),
        DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        ),
    ]

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_awaited_once()

    assert database_status_service.check.await_count == 2

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "database.migrate.success"
    assert event.severity == ReportSeverity.INFO
    assert event.details == ("Schema version: 1 -> 2; application_id: 789")

    interaction.followup.send.assert_awaited_once_with(
        ("Base de données migrée et liée à cette application : `1` → `2`."),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_migrate_rejects_ready_database() -> None:
    """Do not migrate an already up-to-date database."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_migrate_command(
        service,
    )

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.READY,
        current_version=2,
        target_version=2,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        (
            "La base de données est déjà à jour. "
            "Utilise `/claviger database bind` "
            "si son application propriétaire doit être vérifiée."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_migrate_rejects_uninitialized_database() -> None:
    """Require initialization before migration."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_migrate_command(
        service,
    )

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.UNINITIALIZED,
        current_version=0,
        target_version=2,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        (
            "La base de données n'est pas initialisée. "
            "Utilise `/claviger database initialize`."
        ),
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_migrate_rejects_non_owner() -> None:
    """Prevent non-owners from migrating the database."""
    service = Mock(
        spec=RoleDiscoveryService,
    )
    service.get_hierarchy = AsyncMock()

    (
        command,
        database_schema,
        database_status_service,
        report_service,
    ) = get_database_migrate_command(
        service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    database_schema.migrate.assert_not_awaited()
    database_status_service.check.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_database_bind_assigns_current_application() -> None:
    """Bind a ready database to the current Discord application."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )
    role_discovery_service.get_hierarchy = AsyncMock()

    ownership_service = Mock(
        spec=DatabaseOwnershipService,
    )
    ownership_service.bind = AsyncMock()
    ownership_service.get_owner_application_id = AsyncMock(
        return_value=789,
    )

    (
        group,
        _,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        database_ownership_service=ownership_service,
        application_id=789,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "bind",
    )

    assert command is not None

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.READY,
        current_version=8,
        target_version=8,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    ownership_service.bind.assert_awaited_once_with(
        789,
    )

    ownership_service.get_owner_application_id.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "database.bind.success"


@pytest.mark.asyncio
async def test_database_initialize_uses_dynamic_admin_command_name() -> None:
    """Reference the current application's admin namespace in guidance."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )
    role_discovery_service.get_hierarchy = AsyncMock()

    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        command_name="experimentum",
        application_name="Experimentum",
        application_id=789,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "initialize",
    )

    assert command is not None

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.MIGRATION_REQUIRED,
        current_version=7,
        target_version=8,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_schema.initialize.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.followup.send.assert_awaited_once_with(
        (
            "La base de données existe déjà mais nécessite "
            "une migration. Utilise `/experimentum database migrate`."
        ),
        ephemeral=True,
    )
