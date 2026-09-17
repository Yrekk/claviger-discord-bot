from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
)
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationCoordinatorService,
)
from claviger.ui.admin.guild_ai_configuration_view import (
    GuildAIConfigurationChoiceView,
    GuildAIRoleSelectionView,
    run_guild_ai_configuration,
)


def _interaction() -> Mock:
    """Create one deterministic deferred Discord interaction."""

    interaction = Mock(spec=discord.Interaction)
    guild = Mock(spec=discord.Guild)
    guild.id = 123
    user = Mock(spec=discord.Member)
    user.id = 42

    interaction.guild = guild
    interaction.user = user
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    return interaction


def _coordinator(
    state: GuildAIConfigurationInspectionState,
    *,
    role_id: int | None = None,
    role_name: str | None = None,
) -> Mock:
    """Create one AI coordinator exposing a deterministic inspection state."""

    coordinator = Mock(spec=GuildAIConfigurationCoordinatorService)
    configuration = GuildAIConfiguration(
        guild_id=123,
        ai_enabled=(
            False
            if state == GuildAIConfigurationInspectionState.DISABLED
            else (
                None
                if state
                in {
                    GuildAIConfigurationInspectionState.MISSING,
                    GuildAIConfigurationInspectionState.UNCONFIGURED,
                }
                else True
            )
        ),
        ai_role_id=role_id,
    )
    inspection = GuildAIConfigurationInspection(
        guild_id=123,
        state=state,
        configuration=(
            None if state == GuildAIConfigurationInspectionState.MISSING else configuration
        ),
        role_name=role_name,
    )

    coordinator.inspect = AsyncMock(return_value=inspection)
    coordinator.enable = AsyncMock(return_value=inspection)
    coordinator.disable = AsyncMock(return_value=inspection)
    coordinator.assign_role = AsyncMock(return_value=inspection)
    coordinator.create_and_assign_role = AsyncMock(return_value=inspection)
    return coordinator


@pytest.mark.asyncio
async def test_run_ai_configuration_allows_disabled_guild_without_prompt() -> None:
    """Continue immediately when the guild has explicitly opted out of AI."""

    interaction = _interaction()
    coordinator = _coordinator(GuildAIConfigurationInspectionState.DISABLED)
    continuation = AsyncMock()

    ready = await run_guild_ai_configuration(
        interaction,
        coordinator=coordinator,
        continuation=continuation,
    )

    assert ready is True
    interaction.followup.send.assert_not_awaited()
    continuation.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_ai_configuration_prompts_for_unconfigured_guild() -> None:
    """Require an explicit guild-level AI decision before workflow setup."""

    interaction = _interaction()
    coordinator = _coordinator(GuildAIConfigurationInspectionState.UNCONFIGURED)
    continuation = AsyncMock()

    ready = await run_guild_ai_configuration(
        interaction,
        coordinator=coordinator,
        continuation=continuation,
    )

    assert ready is False
    kwargs = interaction.followup.send.await_args.kwargs
    assert isinstance(kwargs["view"], GuildAIConfigurationChoiceView)
    assert "global" in interaction.followup.send.await_args.args[0]


@pytest.mark.asyncio
async def test_run_ai_configuration_opens_role_repair_for_missing_role() -> None:
    """Stop before workflows when enabled AI has no usable reserved role."""

    interaction = _interaction()
    coordinator = _coordinator(
        GuildAIConfigurationInspectionState.ENABLED_ROLE_NOT_FOUND,
        role_id=999,
    )
    continuation = AsyncMock()

    ready = await run_guild_ai_configuration(
        interaction,
        coordinator=coordinator,
        continuation=continuation,
    )

    assert ready is False
    kwargs = interaction.followup.send.await_args.kwargs
    assert isinstance(kwargs["view"], GuildAIRoleSelectionView)
    assert "n'existe plus" in interaction.followup.send.await_args.args[0]
