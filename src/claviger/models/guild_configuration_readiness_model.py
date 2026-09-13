from dataclasses import dataclass
from enum import StrEnum

# Models
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


class GuildConfigurationReadinessState(StrEnum):
    """Describe whether one guild has enough persisted ADMIN configuration."""

    READY = "ready"
    ADMIN_CONFIGURATION_MISSING = "admin_configuration_missing"
    ADMIN_CONFIGURATION_INCOMPLETE = "admin_configuration_incomplete"


@dataclass(frozen=True, slots=True)
class GuildConfigurationReadiness:
    """Describe persisted ADMIN configuration readiness for one Discord guild."""

    guild_id: int
    state: GuildConfigurationReadinessState
    configuration: GuildAdminConfiguration | None

    @property
    def is_ready(self) -> bool:
        """Return whether normal guild runtime features may be considered.

        Returns:
            bool:
                True only when the guild has a complete persisted ADMIN
                configuration.
        """

        return self.state == GuildConfigurationReadinessState.READY
