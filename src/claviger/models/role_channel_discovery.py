from dataclasses import dataclass


@dataclass(frozen=True)
class RoleChannelDiscovery:
    """Represent one Discord role observed for a catalog policy."""

    role_id: int
    role_name: str
    catalog_key: str

    role_manageable: bool

    channel_id: int | None
    channel_name: str | None

    channel_present: bool
    mapping_valid: bool
