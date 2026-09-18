from unittest.mock import AsyncMock, MagicMock

import pytest

from claviger.models.runtime.guild_ai_configuration_model import GuildAIConfiguration
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.runtime.guild_ai_questionnaire_owner_service import (
    GuildAIQuestionnaireOwnerService,
    GuildAIQuestionnaireUnavailableError,
)

pytestmark = pytest.mark.asyncio


def _workflow(
    key: str,
) -> WorkflowDefinition:
    return WorkflowDefinition(
        guild_id=123,
        workflow_key=key,
        command_name=key,
        command_description=f"Configure {key}.",
        title=key.title(),
        description=None,
        policy_key=key,
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(),
    )


def _service(
    *,
    owner: str | None = None,
    ai_enabled: bool | None = True,
    ai_role_id: int | None = 900,
) -> tuple[GuildAIQuestionnaireOwnerService, MagicMock]:
    repository = MagicMock(
        spec=GuildAIQuestionnaireOwnerRepository,
    )
    repository.get = AsyncMock(
        return_value=owner,
    )
    repository.set = AsyncMock()

    ai_repository = MagicMock(
        spec=GuildAIConfigurationRepository,
    )
    ai_repository.get = AsyncMock(
        return_value=GuildAIConfiguration(
            guild_id=123,
            ai_enabled=ai_enabled,
            ai_role_id=ai_role_id,
        )
    )

    workflow_repository = MagicMock(
        spec=WorkflowDefinitionRepository,
    )
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow("gaming"),
            _workflow("member"),
        )
    )

    return (
        GuildAIQuestionnaireOwnerService(
            repository=repository,
            ai_repository=ai_repository,
            workflow_repository=workflow_repository,
        ),
        repository,
    )


async def test_assign_moves_owner_atomically() -> None:
    """Switch ownership by replacing the single guild row."""

    service, repository = _service(
        owner="gaming",
    )

    previous, current = await service.assign(
        guild_id=123,
        workflow_key="member",
    )

    assert previous == "gaming"
    assert current == "member"
    repository.set.assert_awaited_once_with(
        guild_id=123,
        workflow_key="member",
    )


async def test_assign_requires_enabled_ai_role() -> None:
    """Do not expose an AI questionnaire before guild AI has a usable identity."""

    service, repository = _service(
        ai_enabled=False,
        ai_role_id=900,
    )

    with pytest.raises(
        GuildAIQuestionnaireUnavailableError,
    ):
        await service.assign(
            guild_id=123,
            workflow_key="gaming",
        )

    repository.set.assert_not_awaited()
