from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.connection import DatabaseUnavailableError
from claviger.policies.default_policy import (
    SAFE_DEFAULT_POLICY,
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.policies.policy_resolver import PolicyResolver
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)

FALLBACK_GUILD_ID = 123


@pytest.fixture
def repository() -> Mock:
    """Create a mocked guild policy repository."""
    repository = Mock(spec=GuildPolicyRepository)
    repository.get = AsyncMock()

    return repository


@pytest.mark.asyncio
async def test_resolver_uses_safe_default_when_guild_is_not_configured(
    repository: Mock,
) -> None:
    """Use safe defaults when the database has no guild configuration."""
    repository.get.return_value = None

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        456,
    )

    assert policy == SAFE_DEFAULT_POLICY

    repository.get.assert_awaited_once_with(
        456,
    )


@pytest.mark.asyncio
async def test_resolver_applies_partial_database_overrides(
    repository: Mock,
) -> None:
    """Merge configured guild overrides with the safe default policy."""
    repository.get.return_value = GuildPolicyOverrides(
        member_role_name="Citoyen",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        role_management_enabled=True,
    )

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        456,
    )

    assert policy.member_role_name == "Citoyen"
    assert policy.member_interest_prefix == "interest-"
    assert policy.adult_access_prefix == "access-"
    assert policy.role_management_enabled is True

    assert policy.adult_role_name == SAFE_DEFAULT_POLICY.adult_role_name
    assert (
        policy.salutations_channel_name == SAFE_DEFAULT_POLICY.salutations_channel_name
    )
    assert policy.adult_access_enabled is False


@pytest.mark.asyncio
async def test_resolver_preserves_explicit_false_override(
    repository: Mock,
) -> None:
    """Distinguish an explicit False override from an absent override."""
    repository.get.return_value = GuildPolicyOverrides(
        adult_access_enabled=False,
    )

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        456,
    )

    assert policy.adult_access_enabled is False


@pytest.mark.asyncio
async def test_resolver_uses_succumbrae_fallback_when_database_is_unavailable(
    repository: Mock,
) -> None:
    """Keep Succumbrae functional when the database is unavailable."""
    repository.get.side_effect = DatabaseUnavailableError("Database unavailable.")

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        FALLBACK_GUILD_ID,
    )

    assert policy == SUCCUMBRAE_FALLBACK_POLICY


@pytest.mark.asyncio
async def test_resolver_uses_safe_default_for_other_guild_when_database_is_unavailable(
    repository: Mock,
) -> None:
    """Fail safely on other guilds when the database is unavailable."""
    repository.get.side_effect = DatabaseUnavailableError("Database unavailable.")

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        456,
    )

    assert policy == SAFE_DEFAULT_POLICY


@pytest.mark.asyncio
async def test_fallback_guild_does_not_use_emergency_policy_when_database_is_available(
    repository: Mock,
) -> None:
    """Reserve Succumbrae's fallback policy for real database failures."""
    repository.get.return_value = None

    resolver = PolicyResolver(
        repository,
        FALLBACK_GUILD_ID,
    )

    policy = await resolver.resolve(
        FALLBACK_GUILD_ID,
    )

    assert policy == SAFE_DEFAULT_POLICY
    assert policy != SUCCUMBRAE_FALLBACK_POLICY
