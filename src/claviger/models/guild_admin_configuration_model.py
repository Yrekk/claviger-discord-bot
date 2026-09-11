from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuildAdminConfiguration:
    """Describe one guild's persistent administrative Discord routing."""

    guild_id: int

    category_id: int

    command_channel_id: int
    activity_forum_id: int
    error_forum_id: int
