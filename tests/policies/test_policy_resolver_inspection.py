from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.connection import DatabaseUnavailableError
from claviger.models.runtime.guild_policy_inspection_model import GuildPolicySource
from claviger.policies.default_policy import (
    SAFE_DEFAULT_POLICY,
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.runtime.guild_policy_repository import GuildPolicyRepository


@pytest.mark.asyncio
async def test_policy_inspection_identifies_safe_default() -> None:
    repository = Mock(spec=GuildPolicyRepository)
    repository.get = AsyncMock(return_value=None)

    resolver = PolicyResolver(
        repository=repository,
        fallback_guild_id=999,
    )

    inspection = await resolver.inspect(123)

    assert inspection.effective == SAFE_DEFAULT_POLICY
    assert inspection.source == GuildPolicySource.SAFE_DEFAULT
    assert inspection.persisted_override_count == 0


@pytest.mark.asyncio
async def test_policy_inspection_counts_sqlite_overrides() -> None:
    repository = Mock(spec=GuildPolicyRepository)
    repository.get = AsyncMock(
        return_value=GuildPolicyOverrides(
            member_role_name="Custom member",
            role_management_enabled=True,
        )
    )

    resolver = PolicyResolver(
        repository=repository,
        fallback_guild_id=999,
    )

    inspection = await resolver.inspect(123)

    assert inspection.source == GuildPolicySource.SQLITE_OVERRIDES
    assert inspection.persisted_override_count == 2
    assert inspection.effective.member_role_name == "Custom member"
    assert inspection.effective.role_management_enabled is True


@pytest.mark.asyncio
async def test_policy_inspection_identifies_historical_database_fallback() -> None:
    repository = Mock(spec=GuildPolicyRepository)
    repository.get = AsyncMock(
        side_effect=DatabaseUnavailableError("offline"),
    )

    resolver = PolicyResolver(
        repository=repository,
        fallback_guild_id=123,
    )

    inspection = await resolver.inspect(123)

    assert inspection.effective == SUCCUMBRAE_FALLBACK_POLICY
    assert inspection.source == GuildPolicySource.HISTORICAL_FALLBACK
    assert inspection.persisted_override_count == 0
