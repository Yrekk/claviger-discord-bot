from dataclasses import dataclass

from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)


@dataclass(frozen=True)
class CatalogNextSelection:
    """Describe the next incomplete entry from a registered catalog."""

    catalog_key: str
    display_name: str
    entry_name: str
    entry: RoleChannelCatalogEntry
