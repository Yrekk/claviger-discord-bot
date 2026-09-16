from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.models.guild_configuration_metrics_model import (
    GuildConfigurationMetrics,
)
from claviger.models.guild_policy_inspection_model import (
    GuildPolicyInspection,
    GuildPolicySource,
)
from claviger.policies.default_policy import SAFE_DEFAULT_POLICY
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.guild_configuration_metrics_repository import (
    GuildConfigurationMetricsRepository,
)
from claviger.services.admin.admin_configuration_coordinator_service import (
    AdminConfigurationCoordinatorService,
)
from claviger.services.database_ownership_service import DatabaseOwnershipService
from claviger.services.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)


@pytest.mark.asyncio
async def test_configuration_inspection_reads_guild_state_only_after_ownership() -> None:
    guild = Mock(spec=discord.Guild)
    guild.id = 123

    database_status_service = Mock(spec=DatabaseStatusService)
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=10,
            target_version=10,
        )
    )

    ownership_service = Mock(spec=DatabaseOwnershipService)
    ownership_service.get_owner_application_id = AsyncMock(
        return_value=789,
    )

    admin_service = Mock(spec=AdminConfigurationCoordinatorService)
    admin_marker = Mock()
    admin_service.inspect = AsyncMock(
        return_value=admin_marker,
    )

    policy_resolver = Mock(spec=PolicyResolver)
    policy_marker = GuildPolicyInspection(
        effective=SAFE_DEFAULT_POLICY,
        source=GuildPolicySource.SAFE_DEFAULT,
    )
    policy_resolver.inspect = AsyncMock(
        return_value=policy_marker,
    )

    metrics_repository = Mock(spec=GuildConfigurationMetricsRepository)
    metrics_marker = GuildConfigurationMetrics(
        workflow_count=2,
        catalog_count=3,
        context_count=1,
    )
    metrics_repository.get = AsyncMock(
        return_value=metrics_marker,
    )

    service = GuildConfigurationInspectionService(
        database_status_service=database_status_service,
        database_ownership_service=ownership_service,
        admin_configuration_coordinator_service=admin_service,
        policy_resolver=policy_resolver,
        metrics_repository=metrics_repository,
    )

    result = await service.inspect(
        guild,
        application_id=789,
    )

    assert result.database_owned_by_application is True
    assert result.admin is admin_marker
    assert result.policy is policy_marker
    assert result.metrics is metrics_marker

    admin_service.inspect.assert_awaited_once_with(guild)
    policy_resolver.inspect.assert_awaited_once_with(123)
    metrics_repository.get.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_configuration_inspection_does_not_read_foreign_database_guild_state() -> None:
    guild = Mock(spec=discord.Guild)
    guild.id = 123

    database_status_service = Mock(spec=DatabaseStatusService)
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=10,
            target_version=10,
        )
    )

    ownership_service = Mock(spec=DatabaseOwnershipService)
    ownership_service.get_owner_application_id = AsyncMock(
        return_value=456,
    )

    admin_service = Mock(spec=AdminConfigurationCoordinatorService)
    admin_service.inspect = AsyncMock()

    policy_resolver = Mock(spec=PolicyResolver)
    policy_resolver.inspect = AsyncMock()

    metrics_repository = Mock(spec=GuildConfigurationMetricsRepository)
    metrics_repository.get = AsyncMock()

    service = GuildConfigurationInspectionService(
        database_status_service=database_status_service,
        database_ownership_service=ownership_service,
        admin_configuration_coordinator_service=admin_service,
        policy_resolver=policy_resolver,
        metrics_repository=metrics_repository,
    )

    result = await service.inspect(
        guild,
        application_id=789,
    )

    assert result.database_owned_by_application is False
    assert result.admin is None
    assert result.policy is None
    assert result.metrics is None

    admin_service.inspect.assert_not_awaited()
    policy_resolver.inspect.assert_not_awaited()
    metrics_repository.get.assert_not_awaited()
