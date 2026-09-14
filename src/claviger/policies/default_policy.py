from claviger.policies.guild_policy import GuildPolicy

SAFE_DEFAULT_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Adulte (18+)",
    member_interest_prefix="interest-",
    adult_access_prefix="access-",
    salutations_channel_name="salutations",
    adult_access_channel_name="adult-rules",
    role_management_enabled=False,
    adult_access_enabled=False,
)

# Historical fallback:
# Succumbrae is the guild for which Claviger was originally created. This
# code-defined policy intentionally remains available as a known emergency
# baseline when persistent policy storage cannot be reached. Other guilds must
# continue to fail safely to SAFE_DEFAULT_POLICY instead of inheriting it.
SUCCUMBRAE_FALLBACK_POLICY = GuildPolicy(
    member_role_name="Membre",
    adult_role_name="Civis Noctis - 18+",
    member_interest_prefix="interest-",
    adult_access_prefix="access-",
    salutations_channel_name="salutationes",
    adult_access_channel_name="aditus-noctis",
    role_management_enabled=True,
    adult_access_enabled=True,
)
