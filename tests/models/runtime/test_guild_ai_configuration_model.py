import pytest

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
    GuildAIConfigurationState,
)


@pytest.mark.parametrize(
    ("configuration", "expected_state"),
    (
        (
            GuildAIConfiguration(
                guild_id=123,
                ai_enabled=None,
                ai_role_id=None,
            ),
            GuildAIConfigurationState.UNCONFIGURED,
        ),
        (
            GuildAIConfiguration(
                guild_id=123,
                ai_enabled=False,
                ai_role_id=999,
            ),
            GuildAIConfigurationState.DISABLED,
        ),
        (
            GuildAIConfiguration(
                guild_id=123,
                ai_enabled=True,
                ai_role_id=None,
            ),
            GuildAIConfigurationState.ENABLED_ROLE_MISSING,
        ),
        (
            GuildAIConfiguration(
                guild_id=123,
                ai_enabled=True,
                ai_role_id=999,
            ),
            GuildAIConfigurationState.ENABLED,
        ),
    ),
)
def test_state_reflects_persisted_ai_configuration(
    configuration: GuildAIConfiguration,
    expected_state: GuildAIConfigurationState,
) -> None:
    """Expose the four semantic states required by V11 configuration flow."""

    assert configuration.state == expected_state


@pytest.mark.parametrize(
    ("state", "expected_ready"),
    (
        (GuildAIConfigurationInspectionState.MISSING, False),
        (GuildAIConfigurationInspectionState.UNCONFIGURED, False),
        (GuildAIConfigurationInspectionState.DISABLED, True),
        (GuildAIConfigurationInspectionState.ENABLED_ROLE_MISSING, False),
        (GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND, False),
        (GuildAIConfigurationInspectionState.ENABLED_ROLE_UNUSABLE, False),
        (GuildAIConfigurationInspectionState.BOT_MEMBER_UNAVAILABLE, False),
        (GuildAIConfigurationInspectionState.READY, True),
    ),
)
def test_inspection_readiness_controls_workflow_continuation(
    state: GuildAIConfigurationInspectionState,
    expected_ready: bool,
) -> None:
    """Allow workflows only after an explicit disabled or valid enabled state."""

    inspection = GuildAIConfigurationInspection(
        guild_id=123,
        state=state,
        configuration=None,
    )

    assert inspection.is_ready_for_workflows is expected_ready
