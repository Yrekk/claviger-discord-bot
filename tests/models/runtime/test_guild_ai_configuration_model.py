import pytest

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
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
