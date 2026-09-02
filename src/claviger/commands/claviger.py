from discord import app_commands

from claviger.commands.database import create_database_group
from claviger.commands.guild import create_guild_group
from claviger.commands.report import create_report_group
from claviger.commands.roles import create_roles_group
from claviger.database.schema import DatabaseSchema
from claviger.database.status import (
    DatabaseStatusService,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.service import ReportService
from claviger.services.guild_policy_bootstrap import GuildPolicyBootstrapService
from claviger.services.role_classifier import RoleClassifier
from claviger.services.role_discovery import RoleDiscoveryService


def create_claviger_group(
    role_discovery_service: RoleDiscoveryService,
    policy_resolver: PolicyResolver,
    role_classifier: RoleClassifier,
    guild_policy_bootstrap_service: GuildPolicyBootstrapService,
    database_schema: DatabaseSchema,
    database_status_service: DatabaseStatusService,
    report_service: ReportService,
) -> app_commands.Group:
    """Create Claviger's administrative command group."""

    claviger_group = app_commands.Group(
        name="claviger",
        description="Commandes d'administration de Claviger.",
    )
    report_group = create_report_group(
        report_service,
    )

    database_group = create_database_group(
        database_schema,
        database_status_service,
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
    claviger_group.add_command(
        roles_group,
    )

    claviger_group.add_command(
        report_group,
    )

    claviger_group.add_command(
        database_group,
    )
    claviger_group.add_command(
        guild_group,
    )

    return claviger_group
