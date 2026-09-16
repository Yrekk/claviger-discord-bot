import discord

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationDraft,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)
from claviger.models.workflows.workflow_structure_provisioning_model import (
    WorkflowStructureProvisioningResult,
)
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.services.workflows.workflow_configuration_reconciliation_service import (
    WorkflowConfigurationReconciliationService,
)
from claviger.services.workflows.workflow_configuration_validation_service import (
    WorkflowConfigurationValidationService,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)
from claviger.services.workflows.workflow_structure_provisioning_service import (
    WorkflowStructureProvisioningService,
)


class WorkflowConfigurationPersistenceAfterProvisioningError(RuntimeError):
    """Report Discord provisioning that succeeded before SQLite persistence failed."""

    def __init__(
        self,
        *,
        provisioning: WorkflowStructureProvisioningResult,
    ) -> None:
        super().__init__(
            "Workflow Discord provisioning succeeded, but SQLite persistence failed."
        )

        self.provisioning = provisioning


class WorkflowConfigurationCoordinatorService:
    """Coordinate one complete frontend-neutral workflow configuration pass."""

    def __init__(
        self,
        *,
        repository: WorkflowConfigurationRepository,
        validation_service: WorkflowConfigurationValidationService,
        discovery_service: WorkflowStructureDiscoveryService,
        reconciliation_service: WorkflowConfigurationReconciliationService,
        provisioning_service: WorkflowStructureProvisioningService,
    ) -> None:
        self.repository = repository
        self.validation_service = validation_service
        self.discovery_service = discovery_service
        self.reconciliation_service = reconciliation_service
        self.provisioning_service = provisioning_service

    async def discover_resources(
        self,
        guild: discord.Guild,
    ) -> WorkflowStructureDiscoveryResult:
        """Expose the current read-only Discord workflow resource snapshot."""

        return await self.discovery_service.discover(
            guild,
        )

    async def get_ai_preference_role_id(
        self,
        guild_id: int,
    ) -> int | None:
        """Return the guild-wide AI preference role already persisted, if any."""

        return await self.repository.get_ai_preference_role_id(
            guild_id,
        )

    async def configure(
        self,
        *,
        guild: discord.Guild,
        draft: WorkflowConfigurationDraft,
    ) -> WorkflowStructureProvisioningResult:
        """Validate, reconcile, provision and persist one workflow."""

        if draft.guild_id != guild.id:
            raise ValueError(
                "Workflow configuration draft belongs to another Discord guild."
            )

        validated = self.validation_service.validate(
            draft,
        )

        discovery = await self.discovery_service.discover(
            guild,
        )

        persisted_ai_preference_role_id = (
            await self.repository.get_ai_preference_role_id(
                guild.id,
            )
        )

        reconciled = self.reconciliation_service.reconcile(
            configuration=validated,
            discovery=discovery,
            persisted_ai_preference_role_id=(persisted_ai_preference_role_id),
        )

        provisioning = await self.provisioning_service.provision(
            guild=guild,
            configuration=reconciled,
        )

        try:
            await self.repository.save(
                provisioning.configuration,
            )

        except (RuntimeError, ValueError) as error:
            # Discord mutations cannot be rolled back transactionally. Preserve
            # the provisioning result so reporting/UI can explain the exact
            # resources already created or repaired.
            raise WorkflowConfigurationPersistenceAfterProvisioningError(
                provisioning=provisioning,
            ) from error

        return provisioning
