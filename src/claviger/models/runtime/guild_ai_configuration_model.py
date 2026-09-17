from dataclasses import dataclass
from enum import StrEnum


class GuildAIConfigurationState(StrEnum):
    """Describe the persisted AI configuration state for one Discord guild."""

    UNCONFIGURED = "unconfigured"
    DISABLED = "disabled"
    ENABLED_ROLE_MISSING = "enabled_role_missing"
    ENABLED = "enabled"


class GuildAIConfigurationInspectionState(StrEnum):
    """Describe live readiness of one guild's AI configuration."""

    MISSING = "missing"
    UNCONFIGURED = "unconfigured"
    DISABLED = "disabled"
    ENABLED_ROLE_MISSING = "enabled_role_missing"
    ENABLED_ROLE_NOT_FOUND = "enabled_role_not_found"
    ENABLED_ROLE_UNUSABLE = "enabled_role_unusable"
    BOT_MEMBER_UNAVAILABLE = "bot_member_unavailable"
    READY = "ready"


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


@dataclass(frozen=True, slots=True)
class GuildAIConfigurationInspection:
    """Combine persisted AI settings with live Discord role validation."""

    guild_id: int
    state: GuildAIConfigurationInspectionState
    configuration: GuildAIConfiguration | None
    role_name: str | None = None

    @property
    def is_ready_for_workflows(self) -> bool:
        """Return whether config-server may continue into workflow setup."""

        return self.state in {
            GuildAIConfigurationInspectionState.DISABLED,
            GuildAIConfigurationInspectionState.READY,
        }
