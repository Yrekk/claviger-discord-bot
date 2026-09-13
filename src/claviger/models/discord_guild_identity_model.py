from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscordGuildIdentity:
    """Represent the bot's guild-specific Discord identity."""

    guild_id: int
    bot_display_name: str
