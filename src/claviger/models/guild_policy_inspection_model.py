from dataclasses import dataclass
from enum import StrEnum

from claviger.policies.guild_policy import GuildPolicy, GuildPolicyOverrides


class GuildPolicySource(StrEnum):
    """Describe where one guild's effective policy comes from."""

    SAFE_DEFAULT = "safe_default"
    SQLITE_OVERRIDES = "sqlite_overrides"
    HISTORICAL_FALLBACK = "historical_fallback"
    SAFE_DATABASE_FALLBACK = "safe_database_fallback"


@dataclass(frozen=True, slots=True)
class GuildPolicyInspection:
    """Describe the effective guild policy and its persistence source."""

    effective: GuildPolicy
    source: GuildPolicySource
    overrides: GuildPolicyOverrides | None = None

    @property
    def persisted_override_count(self) -> int:
        """Return how many policy fields are explicitly persisted."""

        if self.overrides is None:
            return 0

        values = (
            self.overrides.member_role_name,
            self.overrides.adult_role_name,
            self.overrides.member_interest_prefix,
            self.overrides.adult_access_prefix,
            self.overrides.salutations_channel_name,
            self.overrides.adult_access_channel_name,
            self.overrides.role_management_enabled,
            self.overrides.adult_access_enabled,
        )

        return sum(value is not None for value in values)
