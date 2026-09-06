from dataclasses import dataclass
from typing import Literal

CatalogSyncWarningCode = Literal[
    "missing_channel_mapping",
    "ambiguous_channel_mapping",
]


@dataclass(frozen=True)
class CatalogSyncEntry:
    """Describe technical catalog data ready for create or refresh."""

    role_id: int
    role_name: str
    catalog_key: str

    channel_id: int
    channel_name: str

    role_manageable: bool


@dataclass(frozen=True)
class CatalogStateUpdate:
    """Describe observed state changes without replacing stable identities."""

    role_id: int

    role_name: str | None
    catalog_key: str | None
    channel_name: str | None

    discord_present: bool
    role_manageable: bool
    channel_present: bool
    mapping_valid: bool
    matches_policy: bool


@dataclass(frozen=True)
class CatalogSyncWarning:
    """Describe a catalog role that requires administrator attention."""

    role_id: int
    role_name: str
    code: CatalogSyncWarningCode
    channel_count: int


@dataclass(frozen=True)
class CatalogSyncPlan:
    """Describe every database change required by one catalog sync."""

    creates: tuple[CatalogSyncEntry, ...]
    refreshes: tuple[CatalogSyncEntry, ...]
    state_updates: tuple[CatalogStateUpdate, ...]
    warnings: tuple[CatalogSyncWarning, ...]

    @property
    def change_count(self) -> int:
        """Return the number of planned database writes."""

        return len(self.creates) + len(self.refreshes) + len(self.state_updates)
