import discord

from claviger.database.status import DatabaseState, DatabaseStatusService
from claviger.models.runtime.guild_configuration_inspection_model import (
    GuildConfigurationInspectionResult,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.runtime.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.runtime.database_ownership_service import (
    DatabaseOwnershipService,
)


class GuildConfigurationInspectionService:
    """Build one read-only administrative configuration snapshot."""

    def __init__(
        self,
        *,
        database_status_service: DatabaseStatusService,
        database_ownership_service: DatabaseOwnershipService,
        admin_configuration_coordinator_service: AdminConfigurationCoordinatorService,
        policy_resolver: PolicyResolver,
        metrics_repository: GuildConfigurationMetricsRepository,
    ) -> None:
        self.database_status_service = database_status_service
        self.database_ownership_service = database_ownership_service
        self.admin_configuration_coordinator_service = (
            admin_configuration_coordinator_service
        )
        self.policy_resolver = policy_resolver
        self.metrics_repository = metrics_repository

    async def inspect(
        self,
        guild: discord.Guild,
        *,
        application_id: int,
    ) -> GuildConfigurationInspectionResult:
        """Inspect database, ownership, ADMIN, policy and declarative counters.

        Guild-scoped persisted configuration is trusted only when the database is
        READY and owned by the current Discord application.
        """

        if application_id <= 0:
            raise ValueError("Application ID must be greater than zero.")

        database_status = await self.database_status_service.check()

        owner_application_id: int | None = None
        admin = None
        policy = None
        metrics = None

        if database_status.state == DatabaseState.READY:
            owner_application_id = (
                await self.database_ownership_service.get_owner_application_id()
            )

            if owner_application_id == application_id:
                admin = await self.admin_configuration_coordinator_service.inspect(
                    guild,
                )
                policy = await self.policy_resolver.inspect(
                    guild.id,
                )
                metrics = await self.metrics_repository.get(
                    guild.id,
                )

        return GuildConfigurationInspectionResult(
            guild_id=guild.id,
            application_id=application_id,
            database_status=database_status,
            database_owner_application_id=owner_application_id,
            admin=admin,
            policy=policy,
            metrics=metrics,
        )
