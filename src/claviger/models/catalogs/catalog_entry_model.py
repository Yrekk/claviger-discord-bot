from dataclasses import dataclass
from typing import Literal

CatalogTargetVariant = Literal[
    "base",
    "no_ai",
    "ai",
]


@dataclass(frozen=True, slots=True)
class CatalogEntryTarget:
    """Describe one Discord role target belonging to a logical catalog entry."""

    guild_id: int
    catalog_key: str
    entry_key: str

    role_id: int
    role_name: str

    channel_id: int
    channel_name: str

    variant: CatalogTargetVariant

    enabled: bool
    discord_present: bool
    role_manageable: bool
    channel_present: bool
    mapping_valid: bool
    matches_policy: bool

    @property
    def is_available(self) -> bool:
        """Return whether this concrete target is safe for questionnaire use."""

        return (
            self.enabled
            and self.discord_present
            and self.role_manageable
            and self.channel_present
            and self.mapping_valid
            and self.matches_policy
        )


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """Describe one logical questionnaire entry and every concrete role target."""

    guild_id: int
    catalog_key: str
    entry_key: str

    label: str | None
    description: str | None
    emoji: str | None

    sort_order: int
    enabled: bool

    targets: tuple[CatalogEntryTarget, ...]
