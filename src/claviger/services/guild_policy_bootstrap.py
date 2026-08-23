from claviger.policies.guild_policy import (
    GuildPolicy,
    GuildPolicyOverrides,
)
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)


class GuildBootstrapNotAllowedError(RuntimeError):
    """Raised when bootstrap is requested for a non-bootstrap guild."""


class GuildAlreadyConfiguredError(RuntimeError):
    """Raised when a guild already has persistent policy configuration."""


class GuildPolicyBootstrapService:
    """Create the initial persistent policy for Claviger's bootstrap guild."""

    def __init__(
        self,
        repository: GuildPolicyRepository,
        fallback_guild_id: int,
        bootstrap_policy: GuildPolicy,
    ) -> None:
        self.repository = repository
        self.fallback_guild_id = fallback_guild_id
        self.bootstrap_policy = bootstrap_policy

    async def bootstrap(
        self,
        guild_id: int,
    ) -> GuildPolicyOverrides:
        """Persist the bootstrap policy for an unconfigured fallback guild."""

        if guild_id != self.fallback_guild_id:
            raise GuildBootstrapNotAllowedError(
                "Guild bootstrap is only allowed for the configured "
                "fallback guild."
            )

        existing = await self.repository.get(
            guild_id,
        )

        if existing is not None:
            raise GuildAlreadyConfiguredError(
                f"Guild {guild_id} is already configured."
            )

        policy = self.bootstrap_policy

        overrides = GuildPolicyOverrides(
            member_role_name=policy.member_role_name,
            adult_role_name=policy.adult_role_name,
            member_interest_prefix=policy.member_interest_prefix,
            adult_access_prefix=policy.adult_access_prefix,
            salutations_channel_name=policy.salutations_channel_name,
            adult_rules_channel_name=policy.adult_rules_channel_name,
            role_management_enabled=policy.role_management_enabled,
            adult_access_enabled=policy.adult_access_enabled,
        )

        await self.repository.save(
            guild_id,
            overrides,
        )

        return overrides