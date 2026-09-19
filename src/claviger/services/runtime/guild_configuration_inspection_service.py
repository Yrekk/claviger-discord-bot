import discord

from claviger.database.status import DatabaseState, DatabaseStatusService
from claviger.models.runtime.guild_configuration_inspection_model import (
    GuildConfigurationInspectionResult,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.runtime.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.runtime.database_ownership_service import (
    DatabaseOwnershipService,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
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
        workflow_repository: WorkflowDefinitionRepository | None = None,
        workflow_discovery_service: WorkflowStructureDiscoveryService | None = None,
        ai_repository: GuildAIConfigurationRepository | None = None,
        ai_owner_repository: GuildAIQuestionnaireOwnerRepository | None = None,
    ) -> None:
        self.database_status_service = database_status_service
        self.database_ownership_service = database_ownership_service
        self.admin_configuration_coordinator_service = (
            admin_configuration_coordinator_service
        )
        self.policy_resolver = policy_resolver
        self.metrics_repository = metrics_repository
        self.workflow_repository = workflow_repository
        self.workflow_discovery_service = workflow_discovery_service
        self.ai_repository = ai_repository
        self.ai_owner_repository = ai_owner_repository

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
        workflows = None
        workflow_discovery = None
        ai_configuration = None
        ai_questionnaire_owner_workflow_key = None

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

                if self.workflow_repository is not None:
                    workflows = await self.workflow_repository.list_for_guild(
                        guild.id,
                    )

                if self.workflow_discovery_service is not None:
                    workflow_discovery = (
                        await self.workflow_discovery_service.discover(
                            guild,
                        )
                    )

                if self.ai_repository is not None:
                    ai_configuration = await self.ai_repository.get(
                        guild.id,
                    )

                if self.ai_owner_repository is not None:
                    ai_questionnaire_owner_workflow_key = (
                        await self.ai_owner_repository.get(
                            guild.id,
                        )
                    )

        return GuildConfigurationInspectionResult(
            guild_id=guild.id,
            application_id=application_id,
            database_status=database_status,
            database_owner_application_id=owner_application_id,
            admin=admin,
            policy=policy,
            metrics=metrics,
            workflows=workflows,
            workflow_discovery=workflow_discovery,
            ai_configuration=ai_configuration,
            ai_questionnaire_owner_workflow_key=(
                ai_questionnaire_owner_workflow_key
            ),
        )
