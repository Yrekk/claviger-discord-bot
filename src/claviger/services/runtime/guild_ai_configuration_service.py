import discord

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
    GuildAIConfigurationState,
)
from claviger.repositories.runtime.guild_ai_configuration_repository import (
    GuildAIConfigurationRepository,
)
from claviger.services.roles.role_manageability_service import is_role_manageable


class GuildAIConfigurationError(ValueError):
    """Base error raised for invalid guild AI configuration operations."""


class GuildAINotEnabledError(GuildAIConfigurationError):
    """Raised when a role is assigned before AI is explicitly enabled."""


class GuildAIRoleValidationError(GuildAIConfigurationError):
    """Raised when a selected Discord role cannot be used safely."""


class GuildAIConfigurationService:
    """Configure and validate guild-scoped AI settings independently from UI."""

    def __init__(
        self,
        repository: GuildAIConfigurationRepository,
    ) -> None:
        self.repository = repository

    async def inspect(
        self,
        guild: discord.Guild,
    ) -> GuildAIConfigurationInspection:
        """Return persisted and live readiness for one Discord guild."""

        self._validate_guild_id(guild.id)

        configuration = await self.repository.get(guild.id)

        if configuration is None:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.MISSING,
                configuration=None,
            )

        if configuration.state == GuildAIConfigurationState.UNCONFIGURED:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.UNCONFIGURED,
                configuration=configuration,
            )

        if configuration.state == GuildAIConfigurationState.DISABLED:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.DISABLED,
                configuration=configuration,
            )

        if configuration.state == GuildAIConfigurationState.ENABLED_ROLE_MISSING:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.ENABLED_ROLE_MISSING,
                configuration=configuration,
            )

        role = guild.get_role(configuration.ai_role_id)

        if role is None:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND,
                configuration=configuration,
            )

        bot_member = guild.me

        if bot_member is None:
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.BOT_MEMBER_UNAVAILABLE,
                configuration=configuration,
                role_name=role.name,
            )

        if not self._is_usable_role(role, bot_member):
            return GuildAIConfigurationInspection(
                guild_id=guild.id,
                state=GuildAIConfigurationInspectionState.ENABLED_ROLE_UNUSABLE,
                configuration=configuration,
                role_name=role.name,
            )

        return GuildAIConfigurationInspection(
            guild_id=guild.id,
            state=GuildAIConfigurationInspectionState.READY,
            configuration=configuration,
            role_name=role.name,
        )

    async def enable(
        self,
        guild_id: int,
    ) -> GuildAIConfiguration:
        """Persist explicit AI activation while preserving any stored role ID."""

        self._validate_guild_id(guild_id)
        current = await self.repository.get(guild_id)

        configuration = GuildAIConfiguration(
            guild_id=guild_id,
            ai_enabled=True,
            ai_role_id=None if current is None else current.ai_role_id,
        )
        await self.repository.save(configuration)
        return configuration

    async def disable(
        self,
        guild_id: int,
    ) -> GuildAIConfiguration:
        """Persist explicit AI deactivation while preserving any stored role ID."""

        self._validate_guild_id(guild_id)
        current = await self.repository.get(guild_id)

        configuration = GuildAIConfiguration(
            guild_id=guild_id,
            ai_enabled=False,
            ai_role_id=None if current is None else current.ai_role_id,
        )
        await self.repository.save(configuration)
        return configuration

    async def assign_role(
        self,
        guild: discord.Guild,
        role_id: int,
    ) -> GuildAIConfiguration:
        """Validate and persist the guild-wide AI preference role."""

        self._validate_guild_id(guild.id)

        if role_id <= 0:
            raise GuildAIRoleValidationError(
                "Discord role ID must be greater than zero."
            )

        current = await self.repository.get(guild.id)

        if current is None or current.ai_enabled is not True:
            raise GuildAINotEnabledError(
                "AI must be explicitly enabled before assigning its role."
            )

        role = guild.get_role(role_id)

        if role is None:
            raise GuildAIRoleValidationError(
                "The selected AI role does not exist in this guild."
            )

        bot_member = guild.me

        if bot_member is None:
            raise GuildAIRoleValidationError(
                "Claviger's guild member state is unavailable; role safety cannot be verified."
            )

        if not self._is_usable_role(role, bot_member):
            raise GuildAIRoleValidationError(
                "The selected AI role cannot be safely managed by Claviger."
            )

        configuration = GuildAIConfiguration(
            guild_id=guild.id,
            ai_enabled=True,
            ai_role_id=role.id,
        )
        await self.repository.save(configuration)
        return configuration

    @staticmethod
    def _validate_guild_id(guild_id: int) -> None:
        """Reject invalid Discord guild identifiers before persistence access."""

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

    @staticmethod
    def _is_usable_role(
        role: discord.Role,
        bot_member: discord.Member,
    ) -> bool:
        """Return whether one role is assignable and not Discord's default role."""

        return not role.is_default() and is_role_manageable(role, bot_member)
