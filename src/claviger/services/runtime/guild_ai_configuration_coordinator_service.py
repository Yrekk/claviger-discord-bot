import discord

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfigurationInspection,
)
from claviger.services.runtime.guild_ai_configuration_service import (
    GuildAIConfigurationService,
)
from claviger.services.runtime.guild_ai_role_provisioning_service import (
    GuildAIRoleProvisioningService,
)


class GuildAIConfigurationAfterRoleCreationError(RuntimeError):
    """Report a created Discord role whose AI persistence then failed."""

    def __init__(
        self,
        *,
        role_id: int,
    ) -> None:
        super().__init__(
            "AI role creation succeeded, but guild AI configuration persistence failed."
        )
        self.role_id = role_id


class GuildAIConfigurationCoordinatorService:
    """Coordinate frontend-neutral guild AI configuration use cases."""

    def __init__(
        self,
        *,
        configuration_service: GuildAIConfigurationService,
        provisioning_service: GuildAIRoleProvisioningService,
    ) -> None:
        self.configuration_service = configuration_service
        self.provisioning_service = provisioning_service

    async def inspect(
        self,
        guild: discord.Guild,
    ) -> GuildAIConfigurationInspection:
        """Return the current persisted and live AI readiness for one guild."""

        return await self.configuration_service.inspect(guild)

    async def enable(
        self,
        guild: discord.Guild,
    ) -> GuildAIConfigurationInspection:
        """Enable guild AI and immediately re-evaluate any preserved role."""

        await self.configuration_service.enable(guild.id)
        return await self.configuration_service.inspect(guild)

    async def disable(
        self,
        guild: discord.Guild,
    ) -> GuildAIConfigurationInspection:
        """Disable guild AI while preserving the dormant role identifier."""

        await self.configuration_service.disable(guild.id)
        return await self.configuration_service.inspect(guild)

    async def assign_role(
        self,
        guild: discord.Guild,
        role_id: int,
    ) -> GuildAIConfigurationInspection:
        """Assign one existing manageable Discord role and re-check readiness."""

        await self.configuration_service.assign_role(
            guild,
            role_id,
        )
        return await self.configuration_service.inspect(guild)

    async def create_and_assign_role(
        self,
        guild: discord.Guild,
        name: str,
    ) -> GuildAIConfigurationInspection:
        """Create one AI role, persist it and re-check guild AI readiness."""

        role = await self.provisioning_service.create_role(
            guild,
            name,
        )

        try:
            await self.configuration_service.assign_role(
                guild,
                role.id,
            )

        except Exception as error:
            # Discord role creation cannot be rolled back transactionally with
            # SQLite. Preserve the created role identity so UI/reporting can
            # explain the partial mutation instead of hiding it.
            raise GuildAIConfigurationAfterRoleCreationError(
                role_id=role.id,
            ) from error

        return await self.configuration_service.inspect(guild)
