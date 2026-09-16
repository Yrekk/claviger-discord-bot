import discord


def is_role_manageable(
    role: discord.Role,
    bot_member: discord.Member,
) -> bool:
    """Return whether Claviger can add or remove one Discord role."""

    return not role.managed and role < bot_member.top_role
