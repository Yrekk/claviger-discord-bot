from claviger.policies.guild_policy import GuildPolicy


SAFE_DEFAULT_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Adulte (18+)",
    member_interest_prefix="interest-",
    adult_access_prefix="access-",
    salutations_channel_name="salutations",
    adult_rules_channel_name="adult-rules",
    role_management_enabled=False,
    adult_access_enabled=False,
)


SUCCUMBRAE_FALLBACK_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Civis Noctis - 18+",
    member_interest_prefix="interest-",
    adult_access_prefix="access-",
    salutations_channel_name="salutations",
    adult_rules_channel_name="lex-noctis",
    role_management_enabled=True,
    adult_access_enabled=True,
)