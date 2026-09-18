import discord

from claviger.models.catalogs.catalog_entry_model import CatalogEntry
from claviger.models.runtime.guild_ai_configuration_model import GuildAIConfiguration
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.models.workflows.workflow_questionnaire_model import (
    WorkflowQuestionnaire,
    WorkflowQuestionnaireSubmission,
)
from claviger.models.workflows.workflow_role_execution_result_model import (
    WorkflowRoleExecutionResult,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.catalog_entry_synchronization_service import (
    CatalogEntrySynchronizationService,
)
from claviger.services.workflows.workflow_questionnaire_planner_service import (
    WorkflowQuestionnairePlannerService,
)
from claviger.services.workflows.workflow_role_executor_service import (
    WorkflowRoleExecutorService,
)
from claviger.services.workflows.workflow_role_planner_service import (
    WorkflowRolePlannerService,
)


class WorkflowQuestionnaireCoordinatorError(RuntimeError):
    """Base error raised by the generic questionnaire coordinator."""


class WorkflowQuestionnaireNotFoundError(WorkflowQuestionnaireCoordinatorError):
    """Raised when the requested workflow is absent or disabled."""


class WorkflowQuestionnaireCoordinatorService:
    """Coordinate generic questionnaire preparation, planning and execution."""

    def __init__(
        self,
        *,
        workflow_repository: WorkflowDefinitionRepository,
        catalog_entry_repository: CatalogEntryRepository,
        catalog_sync_service: CatalogEntrySynchronizationService,
        ai_repository: GuildAIConfigurationRepository,
        owner_repository: GuildAIQuestionnaireOwnerRepository,
        questionnaire_planner: WorkflowQuestionnairePlannerService,
        role_planner: WorkflowRolePlannerService,
        role_executor: WorkflowRoleExecutorService,
    ) -> None:
        self.workflow_repository = workflow_repository
        self.catalog_entry_repository = catalog_entry_repository
        self.catalog_sync_service = catalog_sync_service
        self.ai_repository = ai_repository
        self.owner_repository = owner_repository
        self.questionnaire_planner = questionnaire_planner
        self.role_planner = role_planner
        self.role_executor = role_executor

    async def build_questionnaire(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        workflow_key: str,
        ai_preference: bool | None = None,
    ) -> WorkflowQuestionnaire:
        """Build the current questionnaire from fresh persistence and member roles."""

        workflow = await self._load_workflow(
            guild_id=guild.id,
            workflow_key=workflow_key,
        )
        entries_by_catalog = await self._load_catalog_entries(
            workflow,
            guild=guild,
        )
        ai_configuration = await self.ai_repository.get(
            guild.id,
        )
        owner_workflow_key = await self.owner_repository.get(
            guild.id,
        )

        member_role_ids = {
            role.id
            for role in member.roles
        }

        ai_enabled, ai_role_id = self._ai_state(
            ai_configuration,
        )

        return self.questionnaire_planner.build(
            workflow=workflow,
            entries_by_catalog=entries_by_catalog,
            member_role_ids=member_role_ids,
            ai_enabled=ai_enabled,
            ai_role_id=ai_role_id,
            owner_workflow_key=owner_workflow_key,
            requested_ai_preference=ai_preference,
        )

    async def apply_submission(
        self,
        *,
        guild: discord.Guild,
        member: discord.Member,
        workflow_key: str,
        submission: WorkflowQuestionnaireSubmission,
    ) -> WorkflowRoleExecutionResult:
        """Rebuild fresh state, validate the form snapshot and apply its role plan."""

        questionnaire = await self.build_questionnaire(
            guild=guild,
            member=member,
            workflow_key=workflow_key,
            ai_preference=submission.ai_preference,
        )
        member_role_ids = {
            role.id
            for role in member.roles
        }

        plan = self.role_planner.build_plan(
            questionnaire=questionnaire,
            submission=submission,
            member_role_ids=member_role_ids,
        )

        return await self.role_executor.execute(
            member,
            plan,
            reason=f"Workflow /{questionnaire.command_name} questionnaire update",
        )

    async def _load_workflow(
        self,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> WorkflowDefinition:
        normalized_key = workflow_key.strip()

        if not normalized_key:
            raise ValueError("Workflow key cannot be empty.")

        workflow = await self.workflow_repository.get(
            guild_id=guild_id,
            workflow_key=normalized_key,
        )

        if workflow is None or not workflow.enabled:
            raise WorkflowQuestionnaireNotFoundError(
                "Workflow does not exist or is disabled."
            )

        return workflow

    async def _load_catalog_entries(
        self,
        workflow: WorkflowDefinition,
        *,
        guild: discord.Guild,
    ) -> dict[str, tuple[CatalogEntry, ...]]:
        entries_by_catalog: dict[str, tuple[CatalogEntry, ...]] = {}

        for binding in workflow.catalogs:
            if not binding.enabled or not binding.catalog.enabled:
                continue

            entries_by_catalog[binding.catalog.catalog_key] = (
                await self.catalog_sync_service.synchronize(
                    guild=guild,
                    catalog=binding.catalog,
                )
            )

        return entries_by_catalog

    @staticmethod
    def _ai_state(
        configuration: GuildAIConfiguration | None,
    ) -> tuple[bool, int | None]:
        if configuration is None or configuration.ai_enabled is not True:
            return (
                False,
                None,
            )

        if configuration.ai_role_id is None:
            return (
                False,
                None,
            )

        return (
            True,
            configuration.ai_role_id,
        )
