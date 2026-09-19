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
from claviger.models.runtime.guild_ai_configuration_model import GuildAIConfiguration
from claviger.models.workflows.workflow_definition_model import (
    WorkflowCatalogBinding,
    WorkflowDefinition,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.repositories.workflows.workflow_definition_repository import (
    WorkflowDefinitionRepository,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService, RoleHierarchy
from claviger.services.runtime.guild_role_diagnostic_service import (
    GuildRoleDiagnosticService,
)

pytestmark = pytest.mark.asyncio


def _role(
    role_id: int,
    name: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=role_id,
        name=name,
    )


def _workflow() -> WorkflowDefinition:
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

    return WorkflowDefinition(
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
        channel_ids=(200,),
        catalogs=(
            WorkflowCatalogBinding(
                catalog=catalog,
                policy_key=None,
                sort_order=0,
                enabled=True,
            ),
        ),
        primary_role_id=300,
    )


async def test_role_diagnostic_classifies_workflow_roles_and_pattern_anomalies() -> None:
    """Keep configured, anomalous and unrelated roles in separate sections."""

    application = _role(
        1000,
        "Experimentum",
    )
    primary = _role(
        300,
        "Gamer",
    )
    configured_catalog = _role(
        501,
        "gamer-rpg",
    )
    anomaly = _role(
        502,
        "gamer-anomalie",
    )
    loose = _role(
        700,
        "Autre rôle",
    )
    ai_role = _role(
        900,
        "IA",
    )
    unmanageable = _role(
        800,
        "Integration",
    )

    guild = Mock(spec=discord.Guild)
    guild.id = 123
    guild.roles = [
        application,
        primary,
        configured_catalog,
        anomaly,
        loose,
        ai_role,
        unmanageable,
    ]

    role_discovery = Mock(spec=RoleDiscoveryService)
    role_discovery.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=application,
            trusted_roles=[],
            manageable_roles=[
                primary,
                configured_catalog,
                anomaly,
                loose,
                ai_role,
            ],
            unmanageable_roles=[
                unmanageable,
            ],
        )
    )

    channel_discovery = Mock(spec=RoleChannelDiscoveryService)
    channel_discovery.build_snapshot.return_value = GuildRoleChannelSnapshot(
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
            DiscordRoleSnapshot(
                role_id=700,
                role_name="Autre rôle",
                role_manageable=True,
                explicit_channel_ids=(),
            ),
            DiscordRoleSnapshot(
                role_id=900,
                role_name="IA",
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

    workflow_repository = Mock(spec=WorkflowDefinitionRepository)
    workflow_repository.list_for_guild = AsyncMock(
        return_value=(
            _workflow(),
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
                    CatalogEntryTarget(
                        guild_id=123,
                        catalog_key="gamer",
                        entry_key="rpg",
                        role_id=501,
                        role_name="gamer-rpg",
                        channel_id=1501,
                        channel_name="rpg",
                        variant="base",
                        enabled=True,
                        discord_present=True,
                        role_manageable=True,
                        channel_present=True,
                        mapping_valid=True,
                        matches_policy=True,
                    ),
                ),
            ),
        )
    )

    ai_repository = Mock(spec=GuildAIConfigurationRepository)
    ai_repository.get = AsyncMock(
        return_value=GuildAIConfiguration(
            guild_id=123,
            ai_enabled=True,
            ai_role_id=900,
        )
    )

    service = GuildRoleDiagnosticService(
        role_discovery_service=role_discovery,
        role_channel_discovery_service=channel_discovery,
        workflow_repository=workflow_repository,
        catalog_entry_repository=catalog_repository,
        ai_repository=ai_repository,
    )

    result = await service.inspect(
        guild,
    )

    assert result.bot_role_name == "Experimentum"
    assert result.ai_role_name == "IA"
    assert result.workflow_primary_role_names == (
        "Gamer",
    )
    assert result.configured_catalog_role_names == (
        "gamer-rpg",
    )
    assert result.unconfigured_manageable_role_names == (
        "Autre rôle",
    )
    assert result.unmanageable_role_names == (
        "Integration",
    )

    assert len(result.pattern_anomalies) == 1

    role_anomaly = result.pattern_anomalies[0]

    assert role_anomaly.role_name == "gamer-anomalie"
    assert "aucun salon/forum avec visibilité explicite" in role_anomaly.reasons
    assert "absent des targets catalogue en BDD" in role_anomaly.reasons
