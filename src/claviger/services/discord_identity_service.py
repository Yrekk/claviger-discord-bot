import re
import unicodedata

import discord

from claviger.models.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
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
            "Discord application name produces a command name longer "
            "than 32 characters."
        )

    return command_name


class DiscordIdentityService:
    """Resolve application-wide and guild-specific Discord identities."""

    @staticmethod
    def _require_authenticated_user(
        client: discord.Client,
    ) -> discord.ClientUser:
        """Return the authenticated bot user or fail closed."""

        if client.user is None:
            raise RuntimeError("Discord bot identity is unavailable.")

        return client.user

    async def resolve_application(
        self,
        client: discord.Client,
    ) -> DiscordApplicationIdentity:
        """Resolve identity that belongs to the Discord application itself."""

        bot_user = self._require_authenticated_user(
            client,
        )

        application = await client.application_info()

        return DiscordApplicationIdentity(
            application_id=application.id,
            application_name=application.name,
            bot_user_id=bot_user.id,
            admin_command_name=normalize_application_command_name(
                application.name,
            ),
        )

    async def resolve_guild(
        self,
        client: discord.Client,
        guild_id: int,
    ) -> DiscordGuildIdentity:
        """Resolve identity that can vary between Discord guilds."""

        bot_user = self._require_authenticated_user(
            client,
        )

        guild = await client.fetch_guild(
            guild_id,
        )

        bot_member = await guild.fetch_member(
            bot_user.id,
        )

        return DiscordGuildIdentity(
            guild_id=guild_id,
            bot_display_name=bot_member.display_name,
        )

    async def resolve(
        self,
        client: discord.Client,
        guild_id: int,
    ) -> DiscordRuntimeIdentity:
        """Resolve the legacy combined identity for the current runtime."""

        application_identity = await self.resolve_application(
            client,
        )

        guild_identity = await self.resolve_guild(
            client,
            guild_id,
        )

        return DiscordRuntimeIdentity(
            application_id=application_identity.application_id,
            application_name=application_identity.application_name,
            bot_user_id=application_identity.bot_user_id,
            guild_id=guild_identity.guild_id,
            bot_display_name=guild_identity.bot_display_name,
            admin_command_name=application_identity.admin_command_name,
        )
