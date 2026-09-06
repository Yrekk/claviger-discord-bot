from dataclasses import dataclass

from claviger.models.role_channel_catalog import RoleChannelCatalogEntry


@dataclass(frozen=True)
class AdultAccess(RoleChannelCatalogEntry):
    """Represent one configured adult access for a Discord guild."""

    @property
    def access_key(self) -> str:
        """Expose the generic catalog key using adult access terminology."""

        return self.catalog_key
