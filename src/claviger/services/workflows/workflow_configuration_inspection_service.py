from claviger.models.workflows.workflow_configuration_inspection_model import (
    WorkflowConfigurationInspection,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)


class WorkflowConfigurationInspectionService:
    """Build the persisted read-side context used by workflow configuration."""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowDefinitionRepository,
        ai_repository: GuildAIConfigurationRepository,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.ai_repository = ai_repository

    async def inspect(
        self,
        guild_id: int,
        *,
        current_workflow_key: str | None = None,
    ) -> WorkflowConfigurationInspection:
        """Return reservations and workflow bindings for one guild.

        A workflow currently being reconfigured may keep its own primary role.
        Its catalog prefixes remain reserved because questionnaire roles must
        never become a workflow's primary membership role.
        """

        workflows = await self.workflow_repository.list_for_guild(
            guild_id,
        )
        ai_configuration = await self.ai_repository.get(
            guild_id,
        )

        reserved_role_ids = {
            workflow.primary_role_id
            for workflow in workflows
            if workflow.primary_role_id is not None
            and workflow.workflow_key != current_workflow_key
        }

        ai_role_id = (
            ai_configuration.ai_role_id
            if ai_configuration is not None
            else None
        )

        if ai_role_id is not None:
            reserved_role_ids.add(
                ai_role_id,
            )

        reserved_role_prefixes = tuple(
            sorted(
                {
                    binding.catalog.role_prefix
                    for workflow in workflows
                    for binding in workflow.catalogs
                    if binding.catalog.role_prefix
                }
            )
        )

        return WorkflowConfigurationInspection(
            guild_id=guild_id,
            workflows=workflows,
            ai_role_id=ai_role_id,
            reserved_role_ids=frozenset(
                reserved_role_ids,
            ),
            reserved_role_prefixes=reserved_role_prefixes,
        )

    @staticmethod
    def is_role_reserved(
        inspection: WorkflowConfigurationInspection,
        *,
        role_id: int | None,
        role_name: str,
    ) -> bool:
        """Return whether a role conflicts with persisted workflow semantics."""

        if role_id is not None and role_id in inspection.reserved_role_ids:
            return True

        return any(
            role_name.startswith(
                prefix,
            )
            for prefix in inspection.reserved_role_prefixes
        )
