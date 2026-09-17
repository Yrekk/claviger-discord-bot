import discord

from claviger.services.roles.role_manageability_service import is_role_manageable

MAX_DISCORD_ROLE_NAME_LENGTH = 100
PROVISIONING_REASON = "Claviger guild AI role provisioning"


class GuildAIRoleProvisioningError(RuntimeError):
    """Base error raised when the guild-wide AI role cannot be provisioned."""


class GuildAIRoleProvisioningPermissionError(GuildAIRoleProvisioningError):
    """Raised when Claviger cannot safely create the guild-wide AI role."""


class GuildAIRoleProvisioningPartialError(GuildAIRoleProvisioningError):
    """Report a role that was created before post-creation validation failed."""

    def __init__(
        self,
        message: str,
        *,
        role_id: int,
    ) -> None:
        super().__init__(message)
        self.role_id = role_id


class GuildAIRoleProvisioningService:
    """Create the optional guild-wide AI role independently from Discord UI."""

    async def create_role(
        self,
        guild: discord.Guild,
        name: str,
    ) -> discord.Role:
        """Create one manageable role for the guild-wide AI preference."""

        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError("AI role name cannot be empty.")

        if len(normalized_name) > MAX_DISCORD_ROLE_NAME_LENGTH:
            raise ValueError(
                f"AI role name cannot exceed {MAX_DISCORD_ROLE_NAME_LENGTH} characters."
            )

        bot_member = guild.me

        if bot_member is None:
            raise GuildAIRoleProvisioningPermissionError(
                "Claviger's guild member state is unavailable."
            )

        if not bot_member.guild_permissions.manage_roles:
            raise GuildAIRoleProvisioningPermissionError(
                "Claviger does not currently have permission to manage roles."
            )

        try:
            role = await guild.create_role(
                name=normalized_name,
                reason=PROVISIONING_REASON,
            )

        except discord.Forbidden as error:
            raise GuildAIRoleProvisioningPermissionError(
                "Discord refused AI role creation for the current bot permissions."
            ) from error

        except discord.HTTPException as error:
            raise GuildAIRoleProvisioningError(
                "Discord failed while creating the guild-wide AI role."
            ) from error

        if role.is_default() or not is_role_manageable(
            role,
            bot_member,
        ):
            raise GuildAIRoleProvisioningPartialError(
                "The AI role was created but is not safely manageable by Claviger.",
                role_id=role.id,
            )

        return role
