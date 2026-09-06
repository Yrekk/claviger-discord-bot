from dataclasses import dataclass

from claviger.models.role_channel_catalog_model import RoleChannelCatalogEntry


@dataclass(frozen=True)
class MemberInterest(RoleChannelCatalogEntry):
    """Represent one configured member interest for a Discord guild."""

    @property
    def interest_key(self) -> str:
        """Expose the generic catalog key using interest terminology."""

        return self.catalog_key
