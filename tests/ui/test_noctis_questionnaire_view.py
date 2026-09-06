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
    NoctisThemeButton,
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
    interaction.response.defer = AsyncMock()

    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    interaction.edit_original_response = AsyncMock()

    return interaction


def get_theme_button(
    view: NoctisQuestionnaireView,
    theme_key: str,
) -> NoctisThemeButton:
    """Retrieve one questionnaire theme button."""

    for child in view.children:
        if (
            isinstance(
                child,
                NoctisThemeButton,
            )
            and child.theme.theme_key == theme_key
        ):
            return child

    raise AssertionError(f"No Noctis theme button found for {theme_key!r}.")


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

    yuri_button = get_theme_button(
        view,
        "yuri",
    )

    bdsm_button = get_theme_button(
        view,
        "bdsm",
    )

    assert view.selected_theme_keys == ("yuri",)

    assert yuri_button.style == discord.ButtonStyle.success
    assert yuri_button.label is not None
    assert yuri_button.label.startswith("☑")

    assert bdsm_button.style == discord.ButtonStyle.secondary
    assert bdsm_button.label is not None
    assert bdsm_button.label.startswith("☐")

    assert view.include_ai is False
    assert view.toggle_ai.label == "Contenus IA : désactivés"


@pytest.mark.asyncio
async def test_theme_button_toggles_pending_selection() -> None:
    """Toggle themes without using a dropdown menu."""

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

    bdsm_button = get_theme_button(
        view,
        "bdsm",
    )

    interaction = create_interaction()

    await bdsm_button.callback(
        interaction,
    )

    assert view.selected_theme_keys == (
        "yuri",
        "bdsm",
    )

    assert bdsm_button.style == discord.ButtonStyle.success
    assert bdsm_button.label is not None
    assert bdsm_button.label.startswith("☑")

    kwargs = interaction.response.edit_message.await_args.kwargs

    assert kwargs["view"] is view
    assert "Yuri" in kwargs["content"]
    assert "Shibari - BDSM" in kwargs["content"]


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

    kwargs = interaction.response.edit_message.await_args.kwargs

    assert kwargs["view"] is view
    assert "Contenus IA : activés" in kwargs["content"]


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

    kwargs = interaction.response.edit_message.await_args.kwargs

    assert "aucune modification appliquée" in kwargs["content"]
    assert "Yuri" in kwargs["content"]
    assert "Shibari - BDSM" in kwargs["content"]
    assert "Contenus IA : activés" in kwargs["content"]
    assert kwargs["view"] is None


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

    interaction.response.defer.assert_awaited_once()

    coordinator.apply_selection.assert_awaited_once_with(
        interaction.guild,
        interaction.user,
        SUCCUMBRAE_FALLBACK_POLICY,
        ("yuri",),
        include_ai=True,
    )

    assert interaction.edit_original_response.await_count == 2

    progress_kwargs = interaction.edit_original_response.await_args_list[0].kwargs

    assert "Mise à jour de vos accès Noctis" in progress_kwargs["content"]
    assert progress_kwargs["view"] is view

    final_kwargs = interaction.edit_original_response.await_args_list[-1].kwargs

    assert "Vos accès Noctis ont été mis à jour" in final_kwargs["content"]
    assert "4" in final_kwargs["content"]
    assert final_kwargs["view"] is None


@pytest.mark.asyncio
async def test_live_validation_defers_before_applying_roles() -> None:
    """Acknowledge the interaction before role changes complete."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )

    coordinator.apply_selection = AsyncMock(
        return_value=NoctisRoleExecutionResult(
            added_role_ids=(1,),
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

    interaction = create_interaction()

    await view.validate.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once()
    coordinator.apply_selection.assert_awaited_once()

    assert interaction.edit_original_response.await_count == 2

    assert (
        "Mise à jour de vos accès Noctis"
        in interaction.edit_original_response.await_args_list[0].kwargs["content"]
    )

    assert (
        "Vos accès Noctis ont été mis à jour"
        in interaction.edit_original_response.await_args_list[1].kwargs["content"]
    )


@pytest.mark.asyncio
async def test_questionnaire_rejects_other_user() -> None:
    """Prevent another member from interacting with the questionnaire."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )
    coordinator.apply_selection = AsyncMock()

    view = NoctisQuestionnaireView(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
        preview=False,
    )

    interaction = create_interaction(
        user_id=99,
    )

    await view.validate.callback(
        interaction,
    )

    coordinator.apply_selection.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()
