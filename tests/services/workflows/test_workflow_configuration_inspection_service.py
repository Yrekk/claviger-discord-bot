from unittest.mock import AsyncMock, MagicMock

import pytest

from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.runtime.guild_ai_configuration_model import GuildAIConfiguration
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.workflows.workflow_configuration_inspection_service import (
    WorkflowConfigurationInspectionService,
)

pytestmark = pytest.mark.asyncio


def _workflow(
    *,
    workflow_key: str,
    primary_role_id: int,
    role_prefix: str,
) -> WorkflowDefinition:
    """Build one persisted workflow used to exercise reservation rules."""

    return WorkflowDefinition(
        guild_id=123,
        workflow_key=workflow_key,
        command_name=workflow_key,
        command_description=f"Configure {workflow_key}.",
        title=workflow_key.title(),
        description=None,
        policy_key=workflow_key,
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=CatalogDefinition(
                    guild_id=123,
                    catalog_key=f"{workflow_key}-catalog",
                    role_prefix=role_prefix,
                    display_name=workflow_key,
                    entry_name="option",
                    description=None,
                    sort_order=0,
                    enabled=True,
                ),
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        primary_role_id=primary_role_id,
    )


def _service(
    workflows: tuple[WorkflowDefinition, ...],
    *,
    ai_role_id: int | None,
) -> WorkflowConfigurationInspectionService:
    """Create inspection over deterministic persistence mocks."""

    workflow_repository = MagicMock(
        spec=WorkflowDefinitionRepository,
    )
    workflow_repository.list_for_guild = AsyncMock(
        return_value=workflows,
    )

    ai_repository = MagicMock(
        spec=GuildAIConfigurationRepository,
    )
    ai_repository.get = AsyncMock(
        return_value=GuildAIConfiguration(
            guild_id=123,
            ai_enabled=False,
            ai_role_id=ai_role_id,
        )
        if ai_role_id is not None
        else None,
    )

    return WorkflowConfigurationInspectionService(
        workflow_repository=workflow_repository,
        ai_repository=ai_repository,
    )


async def test_inspect_reserves_primary_ai_and_catalog_roles() -> None:
    """Build one reservation snapshot from current V11 persistence."""

    service = _service(
        (
            _workflow(
                workflow_key="member",
                primary_role_id=300,
                role_prefix="interest-",
            ),
        ),
        ai_role_id=900,
    )

    inspection = await service.inspect(
        123,
    )

    assert inspection.reserved_role_ids == frozenset(
        {
            300,
            900,
        }
    )
    assert inspection.reserved_role_prefixes == (
        "interest-",
    )

    assert service.is_role_reserved(
        inspection,
        role_id=900,
        role_name="option-ia",
    )
    assert service.is_role_reserved(
        inspection,
        role_id=301,
        role_name="interest-test",
    )
    assert not service.is_role_reserved(
        inspection,
        role_id=302,
        role_name="Libre",
    )


async def test_reconfiguration_keeps_own_primary_role_but_not_catalog_namespace() -> None:
    """Allow idempotent primary-role reuse without freeing questionnaire roles."""

    service = _service(
        (
            _workflow(
                workflow_key="member",
                primary_role_id=300,
                role_prefix="interest-",
            ),
        ),
        ai_role_id=None,
    )

    inspection = await service.inspect(
        123,
        current_workflow_key="member",
    )

    assert 300 not in inspection.reserved_role_ids
    assert inspection.reserved_role_prefixes == (
        "interest-",
    )
