from dataclasses import dataclass
from typing import Any

from claviger.policies.guild_policy import GuildPolicy
from claviger.repositories.access_catalog_repository import (
    AccessCatalogRepository,
)
from claviger.repositories.interest_catalog_repository import (
    InterestCatalogRepository,
)
from claviger.repositories.role_channel_catalog_repository import (
    RoleChannelCatalogRepository,
)


@dataclass(frozen=True)
class CatalogDefinition:
    """Describe one role-to-channel catalog managed by Claviger."""

    catalog_key: str
    display_name: str
    entry_name: str
    prefix: str
    repository: RoleChannelCatalogRepository[Any]


class CatalogRegistry:
    """Build the role catalog definitions enabled for a guild policy."""

    def __init__(
        self,
        interest_repository: InterestCatalogRepository,
        access_repository: AccessCatalogRepository,
    ) -> None:
        self.interest_repository = interest_repository
        self.access_repository = access_repository

    def for_policy(
        self,
        policy: GuildPolicy,
    ) -> tuple[CatalogDefinition, ...]:
        """Return every catalog using the guild's effective prefixes."""

        return (
            CatalogDefinition(
                catalog_key="member_interests",
                display_name="Member interests",
                entry_name="Member interest",
                prefix=policy.member_interest_prefix,
                repository=self.interest_repository,
            ),
            CatalogDefinition(
                catalog_key="adult_accesses",
                display_name="Adult accesses",
                entry_name="Adult access",
                prefix=policy.adult_access_prefix,
                repository=self.access_repository,
            ),
        )
