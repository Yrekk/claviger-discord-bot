from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.claviger import create_claviger_group
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.database.schema import DatabaseSchema

from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.policies.guild_policy import GuildPolicyOverrides



from claviger.reporting.event import ReportSeverity
from claviger.reporting.service import ReportService

from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)
from claviger.services.guild_policy_bootstrap import (
    GuildAlreadyConfiguredError,
    GuildPolicyBootstrapService,
)



def create_interaction(
    *,
    owner_id: int = 42,
    user_id: int = 42,
    user_display_name: str = "Yrekk",
    guild_id: int = 123,
    guild_name: str = "Succumbrae Atrium",
) -> Mock:
    """Create a mocked guild interaction for Claviger command tests."""
    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = guild_id
    guild.name = guild_name
    guild.owner_id = owner_id

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id
    user.display_name = user_display_name

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
    role = Mock(
        spec=discord.Role,
    )

    role.name = name
    role.position = position

    return role

def create_test_group(
    role_discovery_service: RoleDiscoveryService,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService | None = None,
):
    """Create Claviger's command group with mocked external services."""
    policy_resolver = Mock(
        spec=PolicyResolver,
    )
    policy_resolver.resolve = AsyncMock(
        return_value=SUCCUMBRAE_FALLBACK_POLICY,
    )

    database_schema = Mock(
        spec=DatabaseSchema,
    )
    database_schema.initialize = AsyncMock()
    database_schema.migrate = AsyncMock()

    database_status_service = Mock(
        spec=DatabaseStatusService,
    )
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=2,
            target_version=2,
        )
    )

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

    if guild_policy_bootstrap_service is None:
        guild_policy_bootstrap_service = Mock(
            spec=GuildPolicyBootstrapService,
        )
        guild_policy_bootstrap_service.bootstrap = AsyncMock()

    role_classifier = RoleClassifier()

    group = create_claviger_group(
        role_discovery_service,
        policy_resolver,
        role_classifier,
        guild_policy_bootstrap_service,
        database_schema,
        database_status_service,
        report_service,
    )

    return (
        group,
        policy_resolver,
        database_schema,
        database_status_service,
        report_service,
    )


def get_scan_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger roles scan command."""
    (
        group,
        policy_resolver,
        _,
        _,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    roles_group = group.get_command(
        "roles",
    )

    assert roles_group is not None

    command = roles_group.get_command(
        "scan",
    )

    assert command is not None

    return (
        command,
        policy_resolver,
        report_service,
    )


def get_report_test_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger report test command."""
    (
        group,
        policy_resolver,
        _,
        _,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    report_group = group.get_command(
        "report",
    )

    assert report_group is not None

    command = report_group.get_command(
        "test",
    )

    assert command is not None

    return (
        command,
        policy_resolver,
        report_service,
    )


def get_database_status_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database status command."""
    (
        group,
        _,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "status",
    )

    assert command is not None

    return (
        command,
        database_status_service,
        report_service,
    )


def get_database_initialize_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database initialize command."""
    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "initialize",
    )

    assert command is not None

    return (
        command,
        database_schema,
        database_status_service,
        report_service,
    )

def get_database_migrate_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger database migrate command."""
    (
        group,
        _,
        database_schema,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    command = database_group.get_command(
        "migrate",
    )

    assert command is not None

    return (
        command,
        database_schema,
        database_status_service,
        report_service,
    )

def get_guild_bootstrap_command(
    role_discovery_service: RoleDiscoveryService,
):
    """Create and retrieve the /claviger guild bootstrap command."""

    bootstrap_service = Mock(
        spec=GuildPolicyBootstrapService,
    )
    bootstrap_service.bootstrap = AsyncMock()

    (
        group,
        _,
        _,
        database_status_service,
        report_service,
    ) = create_test_group(
        role_discovery_service,
        guild_policy_bootstrap_service=bootstrap_service,
    )

    guild_group = group.get_command(
        "guild",
    )

    assert guild_group is not None

    command = guild_group.get_command(
        "bootstrap",
    )

    assert command is not None

    return (
        command,
        bootstrap_service,
        database_status_service,
        report_service,
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
        side_effect=RuntimeError(
            "Claviger's highest role could not be found."
        )
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

    assert (
        event.details
        == "Claviger's highest role could not be found."
    )

    interaction.followup.send.assert_awaited_once_with(
        (
            "Impossible d'analyser les rôles : "
            "Claviger's highest role could not be found."
        ),
        ephemeral=True,
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
        (
            "Rapport de test émis. "
            "Vérifie le forum administratif."
        ),
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
            "Base de données initialisée avec succès. "
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
        "La base de données est déjà initialisée et prête.",
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

    database_schema.initialize.side_effect = RuntimeError(
        "Initialization exploded."
    )

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
    assert event.details == "Schema version: 1 -> 2"

    interaction.followup.send.assert_awaited_once_with(
        "Base de données migrée avec succès : `1` → `2`.",
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
        "La base de données est déjà à jour.",
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

    bootstrap_service.bootstrap.side_effect = RuntimeError(
        "Bootstrap exploded."
    )

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