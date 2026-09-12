from unittest.mock import AsyncMock, Mock

import pytest

from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.catalog_next_coordinator_service import (
    CatalogNextCoordinatorService,
    CatalogNotRegisteredError,
)
from claviger.services.catalog_registry_service import (
    CatalogRegistry,
    RuntimeCatalogDefinition,
)


def create_entry(
    *,
    role_id: int,
    role_name: str,
    catalog_key: str,
) -> Mock:
    """Create a mocked catalog entry."""

    entry = Mock(
        spec=RoleChannelCatalogEntry,
    )

    entry.role_id = role_id
    entry.role_name = role_name
    entry.catalog_key = catalog_key

    return entry


def create_definition(
    *,
    catalog_key: str,
    display_name: str,
    entry_name: str,
    prefix: str,
    repository: Mock,
) -> RuntimeCatalogDefinition:
    """Create a legacy runtime catalog definition for coordinator tests."""

    return RuntimeCatalogDefinition(
        catalog_key=catalog_key,
        display_name=display_name,
        entry_name=entry_name,
        prefix=prefix,
        repository=repository,
    )


@pytest.mark.asyncio
async def test_get_next_returns_interest_before_access() -> None:
    """Prefer the first incomplete entry following registry order."""

    interest_repository = Mock()
    interest_repository.get_next_incomplete = AsyncMock()

    access_repository = Mock()
    access_repository.get_next_incomplete = AsyncMock()

    interest_entry = create_entry(
        role_id=100,
        role_name="interest-gaming",
        catalog_key="gaming",
    )

    access_entry = create_entry(
        role_id=101,
        role_name="access-ia-casino",
        catalog_key="ia-casino",
    )

    interest_repository.get_next_incomplete.return_value = interest_entry
    access_repository.get_next_incomplete.return_value = access_entry

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    result = await service.get_next(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    assert result is not None
    assert result.catalog_key == "member_interests"
    assert result.entry is interest_entry

    interest_repository.get_next_incomplete.assert_awaited_once_with(
        123,
    )

    access_repository.get_next_incomplete.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_next_falls_back_to_access_catalog() -> None:
    """Search the next catalog when interests are already complete."""

    interest_repository = Mock()
    interest_repository.get_next_incomplete = AsyncMock(
        return_value=None,
    )

    access_repository = Mock()
    access_repository.get_next_incomplete = AsyncMock()

    access_entry = create_entry(
        role_id=101,
        role_name="access-ia-casino",
        catalog_key="ia-casino",
    )

    access_repository.get_next_incomplete.return_value = access_entry

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    result = await service.get_next(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    assert result is not None
    assert result.catalog_key == "adult_accesses"
    assert result.entry is access_entry

    interest_repository.get_next_incomplete.assert_awaited_once_with(
        123,
    )

    access_repository.get_next_incomplete.assert_awaited_once_with(
        123,
    )


@pytest.mark.asyncio
async def test_get_next_returns_none_when_all_catalogs_are_complete() -> None:
    """Return nothing when every registered catalog is complete."""

    interest_repository = Mock()
    interest_repository.get_next_incomplete = AsyncMock(
        return_value=None,
    )

    access_repository = Mock()
    access_repository.get_next_incomplete = AsyncMock(
        return_value=None,
    )

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    result = await service.get_next(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    assert result is None

    interest_repository.get_next_incomplete.assert_awaited_once_with(
        123,
    )

    access_repository.get_next_incomplete.assert_awaited_once_with(
        123,
    )


@pytest.mark.asyncio
async def test_update_metadata_routes_to_interest_catalog() -> None:
    """Update metadata through the interest catalog repository."""

    interest_repository = Mock()
    interest_repository.update_metadata = AsyncMock(
        return_value="updated-interest",
    )

    access_repository = Mock()
    access_repository.update_metadata = AsyncMock()

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    result = await service.update_metadata(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
        "member_interests",
        100,
        label="Artificial intelligence",
        description="Discussions and resources about artificial intelligence.",
        emoji=None,
    )

    assert result == "updated-interest"

    interest_repository.update_metadata.assert_awaited_once_with(
        123,
        100,
        label="Artificial intelligence",
        description="Discussions and resources about artificial intelligence.",
        emoji=None,
    )

    access_repository.update_metadata.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_metadata_routes_to_access_catalog() -> None:
    """Update metadata through the adult access catalog repository."""

    interest_repository = Mock()
    interest_repository.update_metadata = AsyncMock()

    access_repository = Mock()
    access_repository.update_metadata = AsyncMock(
        return_value="updated-access",
    )

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    result = await service.update_metadata(
        123,
        SUCCUMBRAE_FALLBACK_POLICY,
        "adult_accesses",
        101,
        label="Casino IA",
        description="Accès au contenu casino généré par IA.",
        emoji=None,
    )

    assert result == "updated-access"

    interest_repository.update_metadata.assert_not_awaited()

    access_repository.update_metadata.assert_awaited_once_with(
        123,
        101,
        label="Casino IA",
        description="Accès au contenu casino généré par IA.",
        emoji=None,
    )


@pytest.mark.asyncio
async def test_update_metadata_rejects_unknown_catalog() -> None:
    """Reject metadata updates for an unregistered catalog."""

    interest_repository = Mock()
    interest_repository.update_metadata = AsyncMock()

    access_repository = Mock()
    access_repository.update_metadata = AsyncMock()

    registry = Mock(
        spec=CatalogRegistry,
    )

    registry.for_policy.return_value = (
        create_definition(
            catalog_key="member_interests",
            display_name="Member interests",
            entry_name="Member interest",
            prefix="interest-",
            repository=interest_repository,
        ),
        create_definition(
            catalog_key="adult_accesses",
            display_name="Adult accesses",
            entry_name="Adult access",
            prefix="access-",
            repository=access_repository,
        ),
    )

    service = CatalogNextCoordinatorService(
        registry=registry,
    )

    with pytest.raises(
        CatalogNotRegisteredError,
        match="unknown_catalog",
    ):
        await service.update_metadata(
            123,
            SUCCUMBRAE_FALLBACK_POLICY,
            "unknown_catalog",
            999,
            label="Test",
            description="Test",
            emoji=None,
        )

    interest_repository.update_metadata.assert_not_awaited()
    access_repository.update_metadata.assert_not_awaited()
