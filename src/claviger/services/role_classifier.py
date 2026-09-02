from dataclasses import dataclass

import discord

from claviger.policies.guild_policy import GuildPolicy
from claviger.services.role_discovery import RoleHierarchy


@dataclass(frozen=True)
class RoleClassification:
    """Classify manageable Discord roles according to a guild policy."""

    member_roles: list[discord.Role]
    adult_roles: list[discord.Role]

    interest_roles: list[discord.Role]
    access_roles: list[discord.Role]

    unmanaged_roles: list[discord.Role]


class RoleClassifier:
    """Classify Discord roles according to Claviger's guild policy."""

    def classify(
        self,
        hierarchy: RoleHierarchy,
        policy: GuildPolicy,
    ) -> RoleClassification:
        """Classify manageable roles using the effective guild policy."""

        member_roles: list[discord.Role] = []
        adult_roles: list[discord.Role] = []

        interest_roles: list[discord.Role] = []
        access_roles: list[discord.Role] = []

        unmanaged_roles: list[discord.Role] = []

        for role in hierarchy.manageable_roles:
            if role.name == policy.member_role_name:
                member_roles.append(role)
                continue

            if role.name == policy.adult_role_name:
                adult_roles.append(role)
                continue

            if policy.member_interest_prefix and role.name.startswith(
                policy.member_interest_prefix
            ):
                interest_roles.append(role)
                continue

            if policy.adult_access_prefix and role.name.startswith(
                policy.adult_access_prefix
            ):
                access_roles.append(role)
                continue

            unmanaged_roles.append(role)

        return RoleClassification(
            member_roles=member_roles,
            adult_roles=adult_roles,
            interest_roles=interest_roles,
            access_roles=access_roles,
            unmanaged_roles=unmanaged_roles,
        )
