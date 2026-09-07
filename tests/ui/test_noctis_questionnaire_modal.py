from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import (
    AdultAccessTheme,
)
from claviger.models.noctis_role_execution_result_model import (
    NoctisRoleExecutionResult,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.ui.noctis_questionnaire_modal import (
    NoctisQuestionnaireModal,
)


def create_questionnaire() -> AdultAccessQuestionnaire:
    """Create one testable Noctis theme."""

    access = AdultAccess(
        guild_id=123,
        role_id=10,
        role_name="access-no-ia-yuri",
        catalog_key="no-ia-yuri",
        channel_id=200,
        channel_name="no-ia-yuri",
        label="Yuri",
        description="Contenus Yuri.",
        emoji="🌸",
        sort_order=10,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )

    return AdultAccessQuestionnaire(
        themes=(
            AdultAccessTheme(
                theme_key="yuri",
                base_access=access,
                ai_access=None,
            ),
        ),
        selected_theme_keys=("yuri",),
        include_ai=False,
    )


def create_interaction() -> Mock:
    """Create a mocked modal submission interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123

    member = Mock(
        spec=discord.Member,
    )
    member.id = 42

    interaction.guild = guild
    interaction.user = member

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    interaction.edit_original_response = AsyncMock()

    return interaction


def create_modal() -> tuple[
    NoctisQuestionnaireModal,
    Mock,
]:
    """Create the modal with a mocked workflow coordinator."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    coordinator.apply_selection = AsyncMock(
        return_value=NoctisRoleExecutionResult(
            added_role_ids=(10,),
            removed_role_ids=(),
        )
    )

    modal = NoctisQuestionnaireModal(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
    )

    return (
        modal,
        coordinator,
    )


def test_noctis_modal_restores_existing_selection() -> None:
    """Preselect the member's existing Noctis state."""

    modal, _ = create_modal()

    option = modal.selection_group.options[0]

    assert option.value == "yuri"
    assert option.default is True
    assert modal.ai_checkbox.default is False


@pytest.mark.asyncio
async def test_noctis_modal_live_submission_applies_selection() -> None:
    """Apply the native modal selection through the workflow coordinator."""

    (
        modal,
        coordinator,
    ) = create_modal()

    # Simulate values injected by Discord on modal submission.
    modal.selection_group._values = [
        "yuri",
    ]

    interaction = create_interaction()

    await modal.on_submit(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
        thinking=True,
    )

    coordinator.apply_selection.assert_awaited_once_with(
        interaction.guild,
        interaction.user,
        SUCCUMBRAE_FALLBACK_POLICY,
        ("yuri",),
        include_ai=False,
    )

    assert interaction.edit_original_response.await_count == 2

    progress_message = interaction.edit_original_response.await_args_list[0].kwargs[
        "content"
    ]

    final_message = interaction.edit_original_response.await_args_list[1].kwargs[
        "content"
    ]

    assert "Mise à jour de vos accès Noctis" in progress_message
    assert "Vos accès Noctis ont été mis à jour" in final_message


@pytest.mark.asyncio
async def test_noctis_modal_live_submission_handles_failure() -> None:
    """Give the member a useful retry path when role application fails."""

    (
        modal,
        coordinator,
    ) = create_modal()

    coordinator.apply_selection.side_effect = RuntimeError(
        "Discord role update failed.",
    )

    interaction = create_interaction()

    await modal.on_submit(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
        thinking=True,
    )

    assert interaction.edit_original_response.await_count == 2

    error_message = interaction.edit_original_response.await_args_list[-1].kwargs[
        "content"
    ]

    assert "Impossible de mettre à jour" in error_message
    assert "/noctis" in error_message
