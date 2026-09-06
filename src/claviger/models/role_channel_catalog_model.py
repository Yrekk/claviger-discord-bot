from dataclasses import dataclass


@dataclass(frozen=True)
class RoleChannelCatalogEntry:
    """Represent one catalogued Discord role-to-channel mapping."""

    guild_id: int
    role_id: int
    role_name: str
    catalog_key: str

    channel_id: int
    channel_name: str

    label: str | None
    description: str | None
    emoji: str | None

    sort_order: int
    enabled: bool

    discord_present: bool
    role_manageable: bool
    channel_present: bool
    mapping_valid: bool
    matches_policy: bool

    @property
    def is_configured(self) -> bool:
        """Return whether the required human metadata is configured."""

        return self.label is not None and self.description is not None

    @property
    def is_available(self) -> bool:
        """Return whether the catalog entry is currently usable by Claviger."""

        return (
            self.enabled
            and self.discord_present
            and self.role_manageable
            and self.channel_present
            and self.mapping_valid
            and self.matches_policy
        )

    @property
    def is_publicly_ready(self) -> bool:
        """Return whether the catalog entry can be offered to members."""

        return self.is_configured and self.is_available
