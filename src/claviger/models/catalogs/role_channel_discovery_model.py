from dataclasses import dataclass


@dataclass(frozen=True)
class DiscordRoleSnapshot:
    """Represent one Discord role observed during catalog discovery."""

    role_id: int
    role_name: str
    role_manageable: bool
    explicit_channel_ids: tuple[int, ...]


@dataclass(frozen=True)
class DiscordChannelSnapshot:
    """Represent one Discord content channel observed during discovery."""

    channel_id: int
    channel_name: str


@dataclass(frozen=True)
class GuildRoleChannelSnapshot:
    """Represent the complete Discord state required for catalog sync."""

    roles: tuple[DiscordRoleSnapshot, ...]
    channels: tuple[DiscordChannelSnapshot, ...]
