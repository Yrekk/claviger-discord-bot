from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import AdultAccessTheme
from claviger.models.noctis_role_execution_result_model import (
    NoctisRoleExecutionResult,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.ui.noctis_questionnaire_view import (
    NoctisQuestionnaireView,
    NoctisThemeSelect,
)


def create_access(
    *,
    role_id: int,
    access_key: str,
    label: str,
    description: str,
    emoji: str | None = None,
) -> AdultAccess:
    """Create one publicly ready adult access."""

    return AdultAccess(
        guild_id=123,
        role_id=role_id,
        role_name=f"access-{access_key}",
        catalog_key=access_key,
        channel_id=role_id + 1000,
        channel_name=access_key,
        label=label,
        description=description,
        emoji=emoji,
        sort_order=10,
        enabled=True,
        discord_present=True,
        role_manageable=True,
        channel_present=True,
        mapping_valid=True,
        matches_policy=True,
    )


def create_questionnaire() -> AdultAccessQuestionnaire:
    """Create a questionnaire containing Yuri and BDSM."""

    yuri_base = create_access(
        role_id=10,
        access_key="no-ia-yuri",
        label="Yuri",
        description="Contenus Yuri.",
        emoji="🌸",
    )

    yuri_ai = create_access(
        role_id=11,
        access_key="ia-yuri",
        label="Yuri IA",
        description="Contenus Yuri générés par IA.",
    )

    bdsm_base = create_access(
        role_id=20,
        access_key="no-ia-bdsm",
        label="Shibari - BDSM",
        description="Contenus Shibari et BDSM.",
        emoji="🔗",
    )

    bdsm_ai = create_access(
        role_id=21,
        access_key="ia-bdsm",
        label="Shibari - BDSM IA",
        description="Contenus Shibari et BDSM générés par IA.",
    )

    return AdultAccessQuestionnaire(
        themes=(
            AdultAccessTheme(
                theme_key="yuri",
                base_access=yuri_base,
                ai_access=yuri_ai,
            ),
            AdultAccessTheme(
                theme_key="bdsm",
                base_access=bdsm_base,
                ai_access=bdsm_ai,
            ),
        ),
        selected_theme_keys=("yuri",),
        include_ai=False,
    )


def create_interaction(
    *,
    user_id: int = 42,
) -> Mock:
    """Create a mocked Discord component interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()

    return interaction


def get_theme_select(
    view: NoctisQuestionnaireView,
) -> NoctisThemeSelect:
    """Retrieve the questionnaire theme select."""

    for child in view.children:
        if isinstance(
            child,
            NoctisThemeSelect,
        ):
            return child

    raise AssertionError("No Noctis theme select found.")


@pytest.mark.asyncio
async def test_questionnaire_restores_existing_state() -> None:
    """Restore the member's themes and IA preference in the UI."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=True,
    )

    select = get_theme_select(
        view,
    )

    defaults = {option.value for option in select.options if option.default}

    assert defaults == {
        "yuri",
    }

    assert view.selected_theme_keys == ("yuri",)

    assert view.include_ai is False
    assert view.toggle_ai.label == "Contenus IA : désactivés"


@pytest.mark.asyncio
async def test_theme_select_updates_pending_selection() -> None:
    """Update the pending logical themes without modifying Discord roles."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=True,
    )

    select = get_theme_select(
        view,
    )

    select._values = [
        "bdsm",
    ]

    interaction = create_interaction()

    await select.callback(
        interaction,
    )

    assert view.selected_theme_keys == ("bdsm",)

    interaction.response.edit_message.assert_awaited_once_with(
        view=view,
    )


@pytest.mark.asyncio
async def test_ai_button_toggles_pending_preference() -> None:
    """Toggle IA locally without applying any member role."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=True,
    )

    interaction = create_interaction()

    await view.toggle_ai.callback(
        interaction,
    )

    assert view.include_ai is True
    assert view.toggle_ai.label == "Contenus IA : activés"
    assert view.toggle_ai.style == discord.ButtonStyle.success

    interaction.response.edit_message.assert_awaited_once_with(
        view=view,
    )


@pytest.mark.asyncio
async def test_preview_validation_never_applies_roles() -> None:
    """Validate the real questionnaire UI without mutating Discord."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )
    coordinator.apply_selection = AsyncMock()

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=True,
    )

    view.selected_theme_keys = (
        "yuri",
        "bdsm",
    )
    view.include_ai = True

    interaction = create_interaction()

    await view.validate.callback(
        interaction,
    )

    coordinator.apply_selection.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "aucune modification appliquée" in message
    assert "Yuri" in message
    assert "Shibari - BDSM" in message
    assert "Contenus IA : activés" in message


@pytest.mark.asyncio
async def test_live_validation_applies_selection_through_coordinator() -> None:
    """Apply the final selection only through the workflow coordinator."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    coordinator.apply_selection = AsyncMock(
        return_value=NoctisRoleExecutionResult(
            added_role_ids=(1, 10, 11, 2),
            removed_role_ids=(),
        )
    )

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=False,
    )

    view.selected_theme_keys = ("yuri",)
    view.include_ai = True

    interaction = create_interaction()

    await view.validate.callback(
        interaction,
    )

    coordinator.apply_selection.assert_awaited_once_with(
        interaction.guild,
        interaction.user,
        SUCCUMBRAE_FALLBACK_POLICY,
        ("yuri",),
        include_ai=True,
    )

    message = interaction.response.send_message.await_args.args[0]

    assert "4" in message
