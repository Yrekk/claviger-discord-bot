import discord


class RoleManager:
    """Manage Discord role assignments for guild members."""

    async def add_role(
        self,
        member: discord.Member,
        role: discord.Role,
        *,
        reason: str | None = None,
    ) -> bool:
        """Add a role to a member if they do not already have it."""
        if role in member.roles:
            return False

        await member.add_roles(role, reason=reason)

        return True

    async def remove_role(
        self,
        member: discord.Member,
        role: discord.Role,
        *,
        reason: str | None = None,
    ) -> bool:
        """Remove a role from a member if they currently have it."""
        if role not in member.roles:
            return False

        await member.remove_roles(role, reason=reason)

        return True
