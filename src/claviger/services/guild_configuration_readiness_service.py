# Models
from claviger.models.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
    GuildConfigurationReadinessState,
)

# Repositories
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)


class GuildConfigurationReadinessService:
    """Evaluate persisted ADMIN readiness independently for each guild.

    This service deliberately checks only persisted configuration state.
    Live Discord drift, such as deleted channels or changed permissions, is
    handled by the ADMIN discovery/reconciliation/configuration pipeline.

    A READY application database does not imply that every guild using that
    application is configured. This service provides the per-guild part of
    that distinction.
    """

    def __init__(
        self,
        repository: GuildAdminConfigurationRepository,
    ) -> None:
        """Create the guild configuration readiness service.

        Args:
            repository:
                Repository used to load guild-specific ADMIN routing from the
                application database.

        Returns:
            None:
                The service is initialized without performing database access.
        """

        self.repository = repository

    async def inspect(
        self,
        guild_id: int,
    ) -> GuildConfigurationReadiness:
        """Inspect persisted ADMIN readiness for one Discord guild.

        Args:
            guild_id:
                Positive Discord guild snowflake whose persistent ADMIN
                configuration must be inspected.

        Returns:
            GuildConfigurationReadiness:
                Structured readiness result containing the guild ID, the
                readiness state and the persisted configuration when one
                exists.

        Raises:
            ValueError:
                If ``guild_id`` is not a positive Discord identifier.

            Exception:
                Database access errors raised by the repository are propagated
                unchanged. The caller decides whether the application database
                itself is operational before using this service.
        """

        if guild_id <= 0:
            raise ValueError("Discord guild ID must be greater than zero.")

        # A missing row means the application knows nothing about this guild.
        # This is the normal state immediately after the bot joins a new
        # server and must not be treated as an application database failure.
        configuration = await self.repository.get(
            guild_id,
        )

        if configuration is None:
            return GuildConfigurationReadiness(
                guild_id=guild_id,
                state=(GuildConfigurationReadinessState.ADMIN_CONFIGURATION_MISSING),
                configuration=None,
            )

        # The repository may contain a deliberately partial configuration
        # while config-server waits for explicit semantic choices from the
        # guild administrator. Such a guild is known, but not runtime-ready.
        if not configuration.is_complete:
            return GuildConfigurationReadiness(
                guild_id=guild_id,
                state=(GuildConfigurationReadinessState.ADMIN_CONFIGURATION_INCOMPLETE),
                configuration=configuration,
            )

        return GuildConfigurationReadiness(
            guild_id=guild_id,
            state=GuildConfigurationReadinessState.READY,
            configuration=configuration,
        )
