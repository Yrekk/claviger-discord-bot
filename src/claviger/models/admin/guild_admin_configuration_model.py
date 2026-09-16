from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GuildAdminConfiguration:
    """Describe one guild's persistent administrative Discord routing."""

    guild_id: int

    category_id: int
    activity_forum_id: int

    command_channel_id: int | None
    error_forum_id: int | None

    @property
    def is_complete(self) -> bool:
        """Return whether every normal administrative destination is configured."""

        return self.command_channel_id is not None and self.error_forum_id is not None
