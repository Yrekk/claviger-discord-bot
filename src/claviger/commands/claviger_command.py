from discord import app_commands

from claviger.commands.catalog_command import create_catalog_group
from claviger.commands.database_command import create_database_group
from claviger.commands.guild import create_guild_group
from claviger.commands.report import create_report_group
from claviger.commands.restart_command import (
    RestartCallback,
    create_restart_command,
)
from claviger.commands.roles import create_roles_group
from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.service import ReportService
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
)
from claviger.services.catalog_sync_coordinator_service import (
    CatalogSyncCoordinatorService,
)
from claviger.services.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.guild_policy_bootstrap import GuildPolicyBootstrapService
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService


def _configure_database_command_availability(
    database_group: app_commands.Group,
    *,
    database_state: DatabaseState,
    database_ownership_bound: bool,
) -> None:
    """Expose only database actions that make sense for the current state."""

    available_commands = {
        "status",
    }

    if database_state in (
        DatabaseState.MISSING,
        DatabaseState.UNINITIALIZED,
    ):
        available_commands.add(
            "initialize",
        )

    elif database_state == DatabaseState.MIGRATION_REQUIRED:
        available_commands.add(
            "migrate",
        )

    elif database_state == DatabaseState.READY and not database_ownership_bound:
        available_commands.add(
            "bind",
        )

    for command_name in (
        "initialize",
        "migrate",
        "bind",
    ):
        if command_name not in available_commands:
            database_group.remove_command(
                command_name,
            )


def create_claviger_group(
    role_discovery_service: RoleDiscoveryService,
    policy_resolver: PolicyResolver,
    role_classifier: RoleClassifier,
    catalog_sync_coordinator_service: CatalogSyncCoordinatorService,
    catalog_next_coordinator_service: CatalogNextCoordinatorService,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService,
    database_schema: DatabaseSchema,
    database_status_service: DatabaseStatusService,
    database_ownership_service: DatabaseOwnershipService,
    report_service: ReportService,
    *,
    command_name: str,
    application_name: str,
    application_id: int,
    database_state: DatabaseState,
    database_ownership_bound: bool,
    restart_callback: RestartCallback,
    maintenance_only: bool = False,
) -> app_commands.Group:
    """Create the application's administrative command group."""

    admin_group = app_commands.Group(
        name=command_name,
        description=f"Commandes d'administration de {application_name}.",
    )

    database_group = create_database_group(
        database_schema,
        database_status_service,
        database_ownership_service,
        report_service,
        application_id=application_id,
        admin_command_name=command_name,
    )

    _configure_database_command_availability(
        database_group,
        database_state=database_state,
        database_ownership_bound=database_ownership_bound,
    )

    restart_command = create_restart_command(
        restart_callback,
    )

    admin_group.add_command(
        database_group,
    )

    admin_group.add_command(
        restart_command,
    )

    if maintenance_only:
        return admin_group

    report_group = create_report_group(
        report_service,
    )

    guild_group = create_guild_group(
        guild_policy_bootstrap_service,
        database_status_service,
        report_service,
    )

    roles_group = create_roles_group(
        role_discovery_service,
        policy_resolver,
        role_classifier,
        report_service,
    )

    catalog_group = create_catalog_group(
        catalog_sync_coordinator_service,
        catalog_next_coordinator_service,
        policy_resolver,
        database_status_service,
        report_service,
    )

    admin_group.add_command(
        roles_group,
    )

    admin_group.add_command(
        catalog_group,
    )

    admin_group.add_command(
        report_group,
    )

    admin_group.add_command(
        guild_group,
    )

    return admin_group
