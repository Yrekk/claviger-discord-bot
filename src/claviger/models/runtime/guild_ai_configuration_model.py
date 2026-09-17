from dataclasses import dataclass
from enum import StrEnum


class GuildAIConfigurationState(StrEnum):
    """Describe the persisted AI configuration state for one Discord guild."""

    UNCONFIGURED = "unconfigured"
    DISABLED = "disabled"
    ENABLED_ROLE_MISSING = "enabled_role_missing"
    ENABLED = "enabled"


@dataclass(frozen=True, slots=True)
class GuildAIConfiguration:
    """Store guild-scoped AI capability settings independently from guild policy.

    The V11 schema persists these values in ``guild_settings`` for storage
    convenience, but they form a separate application contract from historical
    policy overrides. A disabled guild may deliberately keep a role identifier;
    the orchestration layer decides whether that role remains usable.
    """

    guild_id: int
    ai_enabled: bool | None
    ai_role_id: int | None

    @property
    def state(self) -> GuildAIConfigurationState:
        """Return the semantic state represented by the persisted values.

        Returns:
            GuildAIConfigurationState:
                UNCONFIGURED when the activation choice is missing, DISABLED
                for an explicit opt-out, ENABLED_ROLE_MISSING when AI is enabled
                without a persisted role, otherwise ENABLED.
        """

        if self.ai_enabled is None:
            return GuildAIConfigurationState.UNCONFIGURED

        if not self.ai_enabled:
            return GuildAIConfigurationState.DISABLED

        if self.ai_role_id is None:
            return GuildAIConfigurationState.ENABLED_ROLE_MISSING

        return GuildAIConfigurationState.ENABLED
