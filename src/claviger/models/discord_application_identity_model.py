from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiscordApplicationIdentity:
    """Represent the authenticated Discord application independently of guilds."""

    application_id: int
    application_name: str
    bot_user_id: int
    admin_command_name: str
