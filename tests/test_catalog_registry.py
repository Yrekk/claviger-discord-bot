from unittest.mock import MagicMock

from claviger.policies.guild_policy import GuildPolicy
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)
from claviger.services.catalog_registry_service import CatalogRegistry


def create_policy(
    *,
    interest_prefix: str = "interest-",
    access_prefix: str = "access-",
) -> GuildPolicy:
    """Create a guild policy for catalog registry tests."""

    return GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Civis Noctis - 18+",
        member_interest_prefix=interest_prefix,
        adult_access_prefix=access_prefix,
        salutations_channel_name="salutations",
        adult_rules_channel_name="lex-noctis",
        role_management_enabled=True,
        adult_access_enabled=True,
    )


def test_registry_returns_interest_and_access_catalogs() -> None:
    """Expose both catalog families through one registry."""

    interest_repository = MagicMock(
        spec=InterestCatalogRepository,
    )
    access_repository = MagicMock(
        spec=AccessCatalogRepository,
    )

    registry = CatalogRegistry(
        interest_repository=interest_repository,
        access_repository=access_repository,
    )

    definitions = registry.for_policy(
        create_policy(),
    )

    assert len(definitions) == 2

    interest = definitions[0]
    access = definitions[1]

    assert interest.catalog_key == "member_interests"
    assert interest.display_name == "Member interests"
    assert interest.entry_name == "Member interest"
    assert interest.prefix == "interest-"
    assert interest.repository is interest_repository

    assert access.catalog_key == "adult_accesses"
    assert access.display_name == "Adult accesses"
    assert access.entry_name == "Adult access"
    assert access.prefix == "access-"
    assert access.repository is access_repository


def test_registry_uses_effective_guild_policy_prefixes() -> None:
    """Never hardcode catalog prefixes outside the effective guild policy."""

    registry = CatalogRegistry(
        interest_repository=MagicMock(
            spec=InterestCatalogRepository,
        ),
        access_repository=MagicMock(
            spec=AccessCatalogRepository,
        ),
    )

    definitions = registry.for_policy(
        create_policy(
            interest_prefix="topic-",
            access_prefix="private-",
        ),
    )

    assert definitions[0].prefix == "topic-"
    assert definitions[1].prefix == "private-"
