import re
import unicodedata

import discord

from claviger.models.discord_runtime_identity_model import (
    DiscordRuntimeIdentity,
)


class InvalidApplicationCommandNameError(RuntimeError):
    """Raised when an application name cannot become a valid command name."""


def normalize_application_command_name(
    application_name: str,
) -> str:
    """Convert a Discord application name into a stable command name."""

    ascii_name = (
        unicodedata.normalize(
            "NFKD",
            application_name,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
        .lower()
    )

    command_name = re.sub(
        r"[^a-z0-9_-]+",
        "-",
        ascii_name,
    )

    command_name = re.sub(
        r"-+",
        "-",
        command_name,
    ).strip("-_")

    if not command_name:
        raise InvalidApplicationCommandNameError(
            "Discord application name cannot produce a valid command name."
        )

    if len(command_name) > 32:
        raise InvalidApplicationCommandNameError(
            "Discord application name produces a command name longer than 32 characters."
        )

    return command_name


class DiscordIdentityService:
    """Resolve Discord application and guild-specific bot identity."""

    async def resolve(
        self,
        client: discord.Client,
        guild_id: int,
    ) -> DiscordRuntimeIdentity:
        """Resolve the authenticated application and its guild display identity."""

        if client.user is None:
            raise RuntimeError("Discord bot identity is unavailable.")

        application = await client.application_info()

        guild = await client.fetch_guild(
            guild_id,
        )

        bot_member = await guild.fetch_member(
            client.user.id,
        )

        return DiscordRuntimeIdentity(
            application_id=application.id,
            application_name=application.name,
            bot_user_id=client.user.id,
            guild_id=guild_id,
            bot_display_name=bot_member.display_name,
            admin_command_name=normalize_application_command_name(
                application.name,
            ),
        )
