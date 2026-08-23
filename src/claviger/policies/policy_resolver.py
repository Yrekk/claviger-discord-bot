from claviger.database.connection import DatabaseUnavailableError
from claviger.policies.default_policy import (
    SAFE_DEFAULT_POLICY,
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.guild_policy import (
    GuildPolicy,
    GuildPolicyOverrides,
)
from claviger.repositories.guild_policy_repository import (
    GuildPolicyRepository,
)


class PolicyResolver:
    """Resolve the effective policy for a Discord guild."""

    def __init__(
        self,
        repository: GuildPolicyRepository,
        fallback_guild_id: int,
    ) -> None:
        self.repository = repository
        self.fallback_guild_id = fallback_guild_id

    async def resolve(
        self,
        guild_id: int,
    ) -> GuildPolicy:
        """Return the effective policy for a guild."""

        try:
            overrides = await self.repository.get(
                guild_id,
            )

        except DatabaseUnavailableError:
            return self._resolve_database_fallback(
                guild_id,
            )

        if overrides is None:
            return SAFE_DEFAULT_POLICY

        return self._apply_overrides(
            SAFE_DEFAULT_POLICY,
            overrides,
        )

    def _resolve_database_fallback(
        self,
        guild_id: int,
    ) -> GuildPolicy:
        """Return the safe policy used while the database is unavailable."""

        if guild_id == self.fallback_guild_id:
            return SUCCUMBRAE_FALLBACK_POLICY

        return SAFE_DEFAULT_POLICY

    @staticmethod
    def _apply_overrides(
        base_policy: GuildPolicy,
        overrides: GuildPolicyOverrides,
    ) -> GuildPolicy:
        """Apply configured overrides to a complete base policy."""

        return GuildPolicy(
            member_role_name=(
                overrides.member_role_name
                if overrides.member_role_name is not None
                else base_policy.member_role_name
            ),
            adult_role_name=(
                overrides.adult_role_name
                if overrides.adult_role_name is not None
                else base_policy.adult_role_name
            ),
            member_interest_prefix=(
                overrides.member_interest_prefix
                if overrides.member_interest_prefix is not None
                else base_policy.member_interest_prefix
            ),
            adult_access_prefix=(
                overrides.adult_access_prefix
                if overrides.adult_access_prefix is not None
                else base_policy.adult_access_prefix
            ),
            salutations_channel_name=(
                overrides.salutations_channel_name
                if overrides.salutations_channel_name is not None
                else base_policy.salutations_channel_name
            ),
            adult_rules_channel_name=(
                overrides.adult_rules_channel_name
                if overrides.adult_rules_channel_name is not None
                else base_policy.adult_rules_channel_name
            ),
            role_management_enabled=(
                overrides.role_management_enabled
                if overrides.role_management_enabled is not None
                else base_policy.role_management_enabled
            ),
            adult_access_enabled=(
                overrides.adult_access_enabled
                if overrides.adult_access_enabled is not None
                else base_policy.adult_access_enabled
            ),
        )