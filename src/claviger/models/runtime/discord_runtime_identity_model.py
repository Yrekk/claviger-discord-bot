from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscordRuntimeIdentity:
    """Represent the authenticated Discord application inside one guild."""

    application_id: int
    application_name: str
    bot_user_id: int
    guild_id: int
    bot_display_name: str
    admin_command_name: str
