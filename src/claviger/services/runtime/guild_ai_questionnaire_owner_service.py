from claviger.models.runtime.guild_ai_questionnaire_owner_model import (
    GuildAIQuestionnaireOwnerInspection,
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


class GuildAIQuestionnaireOwnerError(ValueError):
    """Base error raised while assigning the unique AI questionnaire owner."""


class GuildAIQuestionnaireUnavailableError(GuildAIQuestionnaireOwnerError):
    """Raised when guild AI cannot yet be exposed by a workflow."""


class GuildAIQuestionnaireWorkflowNotFoundError(GuildAIQuestionnaireOwnerError):
    """Raised when the selected workflow does not exist or is disabled."""


class GuildAIQuestionnaireOwnerService:
    """Manage the unique workflow allowed to edit the guild AI preference."""

    def __init__(
        self,
        *,
        repository: GuildAIQuestionnaireOwnerRepository,
        ai_repository: GuildAIConfigurationRepository,
        workflow_repository: WorkflowDefinitionRepository,
    ) -> None:
        self.repository = repository
        self.ai_repository = ai_repository
        self.workflow_repository = workflow_repository

    async def inspect(
        self,
        guild_id: int,
    ) -> GuildAIQuestionnaireOwnerInspection:
        """Return ownership, AI readiness and selectable workflows for one guild."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        owner_workflow_key = await self.repository.get(
            guild_id,
        )
        ai_configuration = await self.ai_repository.get(
            guild_id,
        )
        workflows = tuple(
            workflow
            for workflow in await self.workflow_repository.list_for_guild(
                guild_id,
            )
            if workflow.enabled
        )

        return GuildAIQuestionnaireOwnerInspection(
            guild_id=guild_id,
            owner_workflow_key=owner_workflow_key,
            workflows=workflows,
            ai_enabled=(
                None
                if ai_configuration is None
                else ai_configuration.ai_enabled
            ),
            ai_role_id=(
                None
                if ai_configuration is None
                else ai_configuration.ai_role_id
            ),
        )

    async def assign(
        self,
        *,
        guild_id: int,
        workflow_key: str,
    ) -> tuple[str | None, str]:
        """Atomically assign or move the questionnaire owner."""

        inspection = await self.inspect(
            guild_id,
        )

        if not inspection.can_assign_owner:
            raise GuildAIQuestionnaireUnavailableError(
                "Guild AI must be enabled with a configured role before "
                "assigning its questionnaire workflow."
            )

        normalized_key = workflow_key.strip()

        workflow = next(
            (
                candidate
                for candidate in inspection.workflows
                if candidate.workflow_key == normalized_key
            ),
            None,
        )

        if workflow is None:
            raise GuildAIQuestionnaireWorkflowNotFoundError(
                "The selected workflow does not exist or is disabled."
            )

        previous_owner = inspection.owner_workflow_key

        await self.repository.set(
            guild_id=guild_id,
            workflow_key=workflow.workflow_key,
        )

        return (
            previous_owner,
            workflow.workflow_key,
        )
