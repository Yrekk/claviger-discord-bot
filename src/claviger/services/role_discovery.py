from dataclasses import dataclass, field

import discord


@dataclass(frozen=True)
class RoleHierarchy:
    """Represent the Discord role hierarchy around Claviger's highest role."""

    bot_role: discord.Role
    trusted_roles: list[discord.Role]
    manageable_roles: list[discord.Role]
    unmanageable_roles: list[discord.Role] = field(
        default_factory=list,
    )


def is_trusted_role(
    role: discord.Role,
    bot_role: discord.Role,
) -> bool:
    """Return whether a role currently grants trusted status over Claviger."""

    return role > bot_role and not role.managed and not role.is_default()


def is_manageable_role(
    role: discord.Role,
    bot_role: discord.Role,
) -> bool:
    """Return whether a role is technically manageable by Claviger."""

    return role < bot_role and not role.managed and not role.is_default()


class RoleDiscoveryService:
    """Discover the role hierarchy of a Discord guild."""

    async def get_hierarchy(
        self,
        guild: discord.Guild,
    ) -> RoleHierarchy:
        """Fetch and classify roles around Claviger's highest role."""

        bot_member = guild.me

        if bot_member is None:
            raise RuntimeError("Claviger could not find its own member in this guild.")

        roles = await guild.fetch_roles()

        bot_role_id = bot_member.top_role.id

        bot_role = next(
            (role for role in roles if role.id == bot_role_id),
            None,
        )

        if bot_role is None:
            raise RuntimeError(
                "Claviger's highest role could not be found in the guild roles."
            )

        candidate_roles = [
            role for role in roles if (role.id != bot_role.id and not role.is_default())
        ]

        trusted_roles = [
            role
            for role in candidate_roles
            if is_trusted_role(
                role,
                bot_role,
            )
        ]

        manageable_roles = [
            role
            for role in candidate_roles
            if is_manageable_role(
                role,
                bot_role,
            )
        ]

        unmanageable_roles = [
            role
            for role in candidate_roles
            if not is_manageable_role(
                role,
                bot_role,
            )
        ]

        trusted_roles.sort(
            reverse=True,
        )

        manageable_roles.sort(
            reverse=True,
        )

        unmanageable_roles.sort(
            reverse=True,
        )

        return RoleHierarchy(
            bot_role=bot_role,
            trusted_roles=trusted_roles,
            manageable_roles=manageable_roles,
            unmanageable_roles=unmanageable_roles,
        )
