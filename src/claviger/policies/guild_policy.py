from dataclasses import dataclass


@dataclass(frozen=True)
class GuildPolicy:
    """Define Claviger's effective behavior for a Discord guild."""

    member_role_name: str
    adult_role_name: str
    access_role_prefix: str

    salutations_channel_name: str
    adult_rules_channel_name: str

    role_management_enabled: bool
    adult_access_enabled: bool


@dataclass(frozen=True)
class GuildPolicyOverrides:
    """Define optional guild-specific policy overrides stored in the database."""

    member_role_name: str | None = None
    adult_role_name: str | None = None
    access_role_prefix: str | None = None

    salutations_channel_name: str | None = None
    adult_rules_channel_name: str | None = None

    role_management_enabled: bool | None = None
    adult_access_enabled: bool | None = None