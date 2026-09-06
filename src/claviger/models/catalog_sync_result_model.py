from dataclasses import dataclass

from claviger.models.catalog_sync_model import CatalogSyncPlan


@dataclass(frozen=True)
class CatalogSyncCatalogResult:
    """Describe the synchronization result for one registered catalog."""

    catalog_key: str
    display_name: str
    plan: CatalogSyncPlan

    @property
    def change_count(self) -> int:
        """Return the number of database changes for this catalog."""

        return self.plan.change_count

    @property
    def warning_count(self) -> int:
        """Return the number of synchronization warnings for this catalog."""

        return len(self.plan.warnings)


@dataclass(frozen=True)
class CatalogSyncResult:
    """Describe the result of synchronizing every registered catalog."""

    catalogs: tuple[CatalogSyncCatalogResult, ...]

    @property
    def change_count(self) -> int:
        """Return the total number of database changes."""

        return sum(catalog.change_count for catalog in self.catalogs)

    @property
    def warning_count(self) -> int:
        """Return the total number of synchronization warnings."""

        return sum(catalog.warning_count for catalog in self.catalogs)
