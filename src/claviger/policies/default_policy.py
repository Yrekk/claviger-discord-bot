from dataclasses import dataclass


@dataclass(frozen=True)
class GuildPolicy:
    """Define Claviger's configurable behavior for a Discord guild."""

    member_role_name: str
    adult_role_name: str
    access_role_prefix: str

    salutations_channel_name: str
    adult_rules_channel_name: str

    role_management_enabled: bool
    adult_access_enabled: bool


SAFE_DEFAULT_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Adulte (18+)",
    access_role_prefix="access-",
    salutations_channel_name="salutations",
    adult_rules_channel_name="adult-rules",
    role_management_enabled=False,
    adult_access_enabled=False,
)

##Main discord server is called Succumbrae, with known role and channel names. This is used as a fallback when the database is unavailable.
SUCCUMBRAE_FALLBACK_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Civis Noctis · 18+",
    access_role_prefix="access-",
    salutations_channel_name="salutations",
    adult_rules_channel_name="lex-noctis",
    role_management_enabled=True,
    adult_access_enabled=True,
)