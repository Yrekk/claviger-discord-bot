from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
)
from claviger.models.catalogs.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_questionnaire_owner_repository import (
    GuildAIQuestionnaireOwnerRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)
from claviger.services.runtime.workflow_catalog_diagnostic_service import (
    WorkflowCatalogDiagnosticService,
)

pytestmark = pytest.mark.asyncio


def _target(
    *,
    entry_key: str,
    role_id: int,
    role_name: str,
    channel_id: int,
    channel_name: str,
) -> CatalogEntryTarget:
    return CatalogEntryTarget(
        guild_id=123,
        catalog_key="gamer",
        entry_key=entry_key,
        role_id=role_id,
        role_name=role_name,
        channel_id=channel_id,
        channel_name=channel_name,
        variant="base",
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


async def test_catalog_diagnostic_reports_metadata_sync_and_structure_state() -> None:
    """Expose the exact configuration gaps needed before questionnaire smoke tests."""

    catalog = CatalogDefinition(
        guild_id=123,
        catalog_key="gamer",
        role_prefix="gamer-",
        display_name="Jeux",
        entry_name="Jeu",
        description=None,
        sort_order=0,
        enabled=True,
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="gamer",
        command_name="gamer",
        command_description="Configure tes jeux.",
        title="Gamer",
        description=None,
        policy_key="gamer",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(102,),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=catalog,
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        category_id=100,
        management_channel_id=101,
        primary_role_id=300,
    )

    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            workflow,
        )
    )

    catalog_repository = Mock(spec=CatalogEntryRepository)
    catalog_repository.list_for_catalog = AsyncMock(
        return_value=(
            CatalogEntry(
                guild_id=123,
                catalog_key="gamer",
                entry_key="rpg",
                label="RPG",
                description="Jeux de rôle",
                emoji=None,
                sort_order=0,
                enabled=True,
                targets=(
                    _target(
                        entry_key="rpg",
                        role_id=501,
                        role_name="gamer-rpg",
                        channel_id=1501,
                        channel_name="rpg",
                    ),
                ),
            ),
            CatalogEntry(
                guild_id=123,
                catalog_key="gamer",
                entry_key="strategie",
                label=None,
                description=None,
                emoji=None,
                sort_order=10,
                enabled=True,
                targets=(
                    _target(
                        entry_key="strategie",
                        role_id=503,
                        role_name="gamer-strategie",
                        channel_id=1503,
                        channel_name="strategie",
                    ),
                ),
            ),
        )
    )

    owner_repository = Mock(spec=GuildAIQuestionnaireOwnerRepository)
    owner_repository.get = AsyncMock(
        return_value="gamer",
    )

    discovery = Mock(spec=RoleChannelDiscoveryService)
    discovery.build_snapshot.return_value = GuildRoleChannelSnapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=300,
                role_name="Gamer",
                role_manageable=True,
                explicit_channel_ids=(103,),
            ),
            DiscordRoleSnapshot(
                role_id=501,
                role_name="gamer-rpg",
                role_manageable=True,
                explicit_channel_ids=(1501,),
            ),
            DiscordRoleSnapshot(
                role_id=502,
                role_name="gamer-anomalie",
                role_manageable=True,
                explicit_channel_ids=(),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=103,
                channel_name="discussion-gamer",
            ),
            DiscordChannelSnapshot(
                channel_id=1501,
                channel_name="rpg",
            ),
        ),
    )

    guild = Mock(spec=discord.Guild)
    guild.id = 123
    guild.channels = [
        SimpleNamespace(
            id=100,
            name="GAMING",
        ),
        SimpleNamespace(
            id=101,
            name="gestion-gaming",
        ),
        SimpleNamespace(
            id=102,
            name="gaming",
        ),
        SimpleNamespace(
            id=103,
            name="discussion-gamer",
        ),
        SimpleNamespace(
            id=1501,
            name="rpg",
        ),
    ]

    service = WorkflowCatalogDiagnosticService(
        workflow_repository=workflow_repository,
        catalog_entry_repository=catalog_repository,
        owner_repository=owner_repository,
        discovery_service=discovery,
    )

    result = await service.inspect(
        guild,
    )

    assert len(result.workflows) == 1

    diagnostic = result.workflows[0]

    assert diagnostic.title == "Gamer"
    assert diagnostic.category_name == "GAMING"
    assert diagnostic.management_channel_name == "gestion-gaming"
    assert diagnostic.execution_channel_names == (
        "gaming",
    )
    assert diagnostic.primary_role_name == "Gamer"
    assert diagnostic.primary_role_explicit_channel_names == (
        "discussion-gamer",
    )
    assert diagnostic.ai_questionnaire_owner is True
    assert diagnostic.structure_issues == ()

    catalog_diagnostic = diagnostic.catalogs[0]

    assert catalog_diagnostic.role_prefix == "gamer-"
    assert catalog_diagnostic.linked_channel_names == (
        "rpg",
    )
    assert catalog_diagnostic.entry_count == 2
    assert catalog_diagnostic.complete_entry_count == 1
    assert len(catalog_diagnostic.incomplete_entries) == 1
    assert catalog_diagnostic.incomplete_entries[0].entry_key == "strategie"
    assert catalog_diagnostic.incomplete_entries[0].missing_fields == (
        "label",
        "description",
    )
    assert catalog_diagnostic.incomplete_entries[0].target_role_names == (
        "gamer-strategie",
    )
    assert catalog_diagnostic.unsynced_role_names == (
        "gamer-anomalie",
    )

    issues_by_role = {
        issue.role_name: issue.reasons
        for issue in catalog_diagnostic.role_issues
    }

    assert "absent de la BDD" in issues_by_role["gamer-anomalie"]
    assert "aucun salon/forum explicite" in issues_by_role["gamer-anomalie"]
    assert "rôle BDD absent de Discord" in issues_by_role["gamer-strategie"]
