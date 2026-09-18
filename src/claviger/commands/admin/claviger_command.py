from discord import app_commands

from claviger.commands.admin.admin_command_group import GuildAdminCommandGroup
from claviger.commands.admin.config_command import create_config_group
from claviger.commands.admin.config_server_command import (
    create_config_server_command,
)
from claviger.commands.admin.database_command import create_database_group
from claviger.commands.admin.guild import create_guild_group
from claviger.commands.admin.report import create_report_group
from claviger.commands.admin.restart_command import (
    RestartCallback,
    create_restart_command,
)
from claviger.commands.admin.roles import create_roles_group
from claviger.commands.admin.workflow import create_workflow_group
from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseState,
    DatabaseStatusService,
)
from claviger.reporting.service import ReportService
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationCoordinatorService,
)
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
)
from claviger.services.runtime.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)
from claviger.services.runtime.guild_policy_bootstrap import GuildPolicyBootstrapService
from claviger.services.workflows.workflow_configuration_coordinator_service import (
    WorkflowConfigurationCoordinatorService,
)


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
    guild_policy_bootstrap_service: GuildPolicyBootstrapService,
    database_schema: DatabaseSchema,
    database_status_service: DatabaseStatusService,
    database_ownership_service: DatabaseOwnershipService,
    report_service: ReportService,
    *,
    admin_configuration_coordinator_service: AdminConfigurationCoordinatorService,
    ai_configuration_coordinator_service: GuildAIConfigurationCoordinatorService,
    workflow_configuration_coordinator_service: WorkflowConfigurationCoordinatorService,
    ai_questionnaire_owner_service: GuildAIQuestionnaireOwnerService | None = None,
    guild_configuration_inspection_service: (
        GuildConfigurationInspectionService | None
    ) = None,
    command_name: str,
    application_name: str,
    application_id: int,
    database_state: DatabaseState,
    database_ownership_bound: bool,
    restart_callback: RestartCallback,
    admin_command_channel_id: int | None = None,
    maintenance_only: bool = False,
) -> app_commands.Group:
    """Create the application's administrative command group."""

    routing_inspector = (
        admin_configuration_coordinator_service.inspect
        if database_state == DatabaseState.READY and database_ownership_bound
        else None
    )

    admin_group = GuildAdminCommandGroup(
        name=command_name,
        description=f"Commandes d'administration de {application_name}.",
        routing_inspector=routing_inspector,
    )

    database_group = create_database_group(
        database_schema,
        database_status_service,
        database_ownership_service,
        report_service,
        admin_configuration_coordinator_service=(
            admin_configuration_coordinator_service
        ),
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

    config_server_command = create_config_server_command(
        admin_configuration_coordinator_service,
        ai_configuration_coordinator_service,
        workflow_configuration_coordinator_service,
        admin_command_name=command_name,
        database_state=database_state,
        database_ownership_bound=database_ownership_bound,
        report_service=report_service,
        ai_questionnaire_owner_service=ai_questionnaire_owner_service,
    )

    admin_group.add_command(
        database_group,
    )
    admin_group.add_command(
        restart_command,
    )
    admin_group.add_command(
        config_server_command,
    )

    if guild_configuration_inspection_service is not None:
        config_group = create_config_group(
            guild_configuration_inspection_service,
            report_service,
            application_name=application_name,
            application_id=application_id,
        )

        admin_group.add_command(
            config_group,
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
        report_service,
    )

    if ai_questionnaire_owner_service is not None:
        workflow_group = create_workflow_group(
            ai_questionnaire_owner_service,
            report_service,
        )
        admin_group.add_command(
            workflow_group,
        )

    admin_group.add_command(
        roles_group,
    )
    admin_group.add_command(
        report_group,
    )
    admin_group.add_command(
        guild_group,
    )

    return admin_group
