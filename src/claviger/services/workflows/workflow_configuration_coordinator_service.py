from dataclasses import replace

import discord

from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationDraft,
)
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
)
from claviger.models.workflows.workflow_configuration_inspection_model import (
    WorkflowConfigurationInspection,
)
from claviger.models.workflows.workflow_structure_provisioning_model import (
    WorkflowStructureProvisioningResult,
)
from claviger.repositories.workflows.workflow_configuration_repository import (
    WorkflowConfigurationRepository,
)
from claviger.services.workflows.workflow_configuration_inspection_service import (
    WorkflowConfigurationInspectionService,
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
        inspection_service: WorkflowConfigurationInspectionService,
        reconciliation_service: WorkflowConfigurationReconciliationService,
        provisioning_service: WorkflowStructureProvisioningService,
    ) -> None:
        self.repository = repository
        self.validation_service = validation_service
        self.discovery_service = discovery_service
        self.inspection_service = inspection_service
        self.reconciliation_service = reconciliation_service
        self.provisioning_service = provisioning_service

    async def discover_resources(
        self,
        guild: discord.Guild,
    ) -> WorkflowStructureDiscoveryResult:
        """Expose Discord resources filtered and annotated by V11 persistence."""

        return await self._discover_resources(
            guild,
            current_workflow_key=None,
        )

    async def _discover_resources(
        self,
        guild: discord.Guild,
        *,
        current_workflow_key: str | None,
    ) -> WorkflowStructureDiscoveryResult:
        """Combine pure Discord discovery with persisted workflow reservations."""

        discovery = await self.discovery_service.discover(
            guild,
        )
        inspection = await self.inspection_service.inspect(
            guild.id,
            current_workflow_key=current_workflow_key,
        )

        manageable_roles = tuple(
            role
            for role in discovery.manageable_roles
            if not self.inspection_service.is_role_reserved(
                inspection,
                role_id=role.role_id,
                role_name=role.role_name,
            )
        )

        workflow_candidates = tuple(
            self._annotate_candidate(
                candidate,
                inspection=inspection,
            )
            for candidate in discovery.workflow_candidates
        )

        return replace(
            discovery,
            manageable_roles=manageable_roles,
            workflow_candidates=workflow_candidates,
        )

    @staticmethod
    def _annotate_candidate(
        candidate: WorkflowStructureCandidate,
        *,
        inspection: WorkflowConfigurationInspection,
    ) -> WorkflowStructureCandidate:
        """Describe existing workflow bindings without forbidding structure reuse."""

        protected_ids = {
            channel.channel_id
            for channel in candidate.protected_channels
        }
        interactive_ids = {
            channel.channel_id
            for channel in candidate.interactive_channels
        }

        command_names = tuple(
            sorted(
                workflow.command_name
                for workflow in inspection.workflows
                if workflow.category_id == candidate.category.category_id
                and workflow.management_channel_id in protected_ids
                and bool(
                    interactive_ids.intersection(
                        workflow.channel_ids,
                    )
                )
            )
        )

        return replace(
            candidate,
            configured_command_names=command_names,
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

        discovery = await self._discover_resources(
            guild,
            current_workflow_key=validated.workflow_key,
        )

        reconciled = self.reconciliation_service.reconcile(
            configuration=validated,
            discovery=discovery,
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
