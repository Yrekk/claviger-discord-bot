from unittest.mock import AsyncMock, Mock

import pytest

from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.guild_policy import GuildPolicyOverrides
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)
from claviger.services.guild_policy_bootstrap import (
    GuildAlreadyConfiguredError,
    GuildBootstrapNotAllowedError,
    GuildPolicyBootstrapService,
)


def create_service(
    *,
    fallback_guild_id: int = 123,
) -> tuple[
    GuildPolicyBootstrapService,
    Mock,
]:
    """Create a bootstrap service with a mocked repository."""

    repository = Mock(
        spec=GuildPolicyRepository,
    )

    repository.get = AsyncMock(
        return_value=None,
    )
    repository.save = AsyncMock()

    service = GuildPolicyBootstrapService(
        repository=repository,
        fallback_guild_id=fallback_guild_id,
        bootstrap_policy=SUCCUMBRAE_FALLBACK_POLICY,
    )

    return (
        service,
        repository,
    )


@pytest.mark.asyncio
async def test_bootstrap_persists_complete_fallback_policy() -> None:
    """Persist the complete fallback policy for the bootstrap guild."""

    service, repository = create_service()

    overrides = await service.bootstrap(
        123,
    )

    repository.get.assert_awaited_once_with(
        123,
    )

    repository.save.assert_awaited_once_with(
        123,
        overrides,
    )

    assert overrides == GuildPolicyOverrides(
        member_role_name="Membre",
        adult_role_name="Civis Noctis - 18+",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        salutations_channel_name="salutationes",
        adult_access_channel_name="aditus-noctis",
        role_management_enabled=True,
        adult_access_enabled=True,
    )


@pytest.mark.asyncio
async def test_bootstrap_rejects_already_configured_guild() -> None:
    """Never overwrite an existing guild configuration."""

    service, repository = create_service()

    repository.get.return_value = GuildPolicyOverrides(
        member_role_name="Membre",
    )

    with pytest.raises(
        GuildAlreadyConfiguredError,
        match="already configured",
    ):
        await service.bootstrap(
            123,
        )

    repository.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_bootstrap_rejects_non_fallback_guild() -> None:
    """Prevent bootstrap from seeding an unrelated Discord guild."""

    service, repository = create_service(
        fallback_guild_id=123,
    )

    with pytest.raises(
        GuildBootstrapNotAllowedError,
        match="only allowed",
    ):
        await service.bootstrap(
            456,
        )

    repository.get.assert_not_awaited()
    repository.save.assert_not_awaited()
