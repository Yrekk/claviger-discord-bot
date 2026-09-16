from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogDefinition:
    """Describe one guild-specific declarative role catalog."""

    guild_id: int
    catalog_key: str

    role_prefix: str

    display_name: str
    entry_name: str
    description: str | None

    sort_order: int
    enabled: bool
