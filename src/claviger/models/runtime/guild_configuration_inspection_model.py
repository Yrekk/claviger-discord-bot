from dataclasses import dataclass

from claviger.database.status import DatabaseStatus
from claviger.models.admin.admin_configuration_inspection_model import (
    AdminConfigurationInspectionResult,
)
from claviger.models.runtime.guild_configuration_metrics_model import (
    GuildConfigurationMetrics,
)
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
)
from claviger.models.runtime.guild_policy_inspection_model import (
    GuildPolicyInspection,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowStructureDiscoveryResult,
)


@dataclass(frozen=True, slots=True)
class GuildConfigurationInspectionResult:
    """Describe application configuration health for one Discord guild."""

    guild_id: int
    application_id: int

    database_status: DatabaseStatus
    database_owner_application_id: int | None

    admin: AdminConfigurationInspectionResult | None
    policy: GuildPolicyInspection | None
    metrics: GuildConfigurationMetrics | None

    workflows: tuple[WorkflowDefinition, ...] | None = None
    workflow_discovery: WorkflowStructureDiscoveryResult | None = None
    ai_configuration: GuildAIConfiguration | None = None
    ai_questionnaire_owner_workflow_key: str | None = None

    @property
    def database_owned_by_application(self) -> bool:
        """Return whether the READY database belongs to this application."""

        return self.database_owner_application_id == self.application_id
