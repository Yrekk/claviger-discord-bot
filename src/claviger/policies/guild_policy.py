from dataclasses import dataclass


@dataclass(frozen=True)
class GuildPolicy:
    """Define Claviger's effective behavior for a Discord guild."""

    member_role_name: str
    adult_role_name: str

    member_interest_prefix: str
    adult_access_prefix: str

    salutations_channel_name: str
    adult_access_channel_name: str

    role_management_enabled: bool
    adult_access_enabled: bool


@dataclass(frozen=True)
class GuildPolicyOverrides:
    """Define optional guild-specific policy overrides stored in the database."""

    member_role_name: str | None = None
    adult_role_name: str | None = None

    member_interest_prefix: str | None = None
    adult_access_prefix: str | None = None

    salutations_channel_name: str | None = None
    adult_access_channel_name: str | None = None

    role_management_enabled: bool | None = None
    adult_access_enabled: bool | None = None
