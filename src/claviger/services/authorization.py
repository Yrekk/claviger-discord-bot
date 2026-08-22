from enum import StrEnum

import discord

from claviger.services.role_discovery import is_trusted_role


class Capability(StrEnum):
    """Capabilities that can be granted by Claviger's authorization system."""

    SAY = "say"
    SAY_PLAIN = "say.plain"
    ROLE_SCAN = "role.scan"


DEFAULT_TRUSTED_CAPABILITIES = frozenset(
    {
        Capability.SAY,
    }
)


class AuthorizationService:
    """Determine whether a Discord member can use a Claviger capability."""

    async def is_allowed(
        self,
        member: discord.Member,
        guild: discord.Guild,
        capability: Capability,
    ) -> bool:
        """Return whether the member is allowed to use a capability."""

        if member.id == guild.owner_id:
            return True

        if capability not in DEFAULT_TRUSTED_CAPABILITIES:
            return False

        bot_member = guild.me

        if bot_member is None:
            return False

        bot_role = bot_member.top_role

        return any(
            is_trusted_role(
                role,
                bot_role,
            )
            for role in member.roles
        )