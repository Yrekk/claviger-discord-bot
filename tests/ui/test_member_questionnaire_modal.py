from unittest.mock import AsyncMock, Mock, PropertyMock, patch

import discord
import pytest

from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.models.member_role_execution_result_model import (
    MemberRoleExecutionResult,
)
from claviger.models.role_channel_catalog_model import (
    RoleChannelCatalogEntry,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.member_workflow_coordinator_service import (
    MemberWorkflowCoordinatorService,
)
from claviger.ui.catalog_selection_modal import (
    CatalogSelectionModal,
)
from claviger.ui.member_questionnaire_modal import (
    MemberQuestionnaireModal,
)


def create_interest(
    *,
    key: str,
    label: str,
    role_id: int,
    description: str | None = None,
    emoji: str | None = None,
) -> Mock:
    """Create a catalog interest for member modal tests."""

    interest = Mock(
        spec=RoleChannelCatalogEntry,
    )

    interest.catalog_key = key
    interest.label = label
    interest.role_id = role_id
    interest.description = description
    interest.emoji = emoji

    return interest


def create_questionnaire() -> MemberInterestQuestionnaire:
    """Create a deterministic member questionnaire."""

    return MemberInterestQuestionnaire(
        interests=(
            create_interest(
                key="musicae",
                label="Musique",
                role_id=10,
                description="Pour parler musique.",
                emoji="🎵",
            ),
            create_interest(
                key="codex",
                label="Lecture",
                role_id=20,
                description="Livres, mangas et autres lectures.",
                emoji="📚",
            ),
        ),
        selected_interest_keys=("musicae",),
    )


def create_coordinator() -> Mock:
    """Create a mocked member workflow coordinator."""

    coordinator = Mock(
        spec=MemberWorkflowCoordinatorService,
    )

    coordinator.apply_selection = AsyncMock()

    return coordinator


def create_interaction() -> Mock:
    """Create a mocked guild modal interaction."""

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
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()

    interaction.edit_original_response = AsyncMock()

    return interaction


def test_member_modal_restores_existing_interest_selection() -> None:
    """Preselect interests already held by the Discord member."""

    modal = MemberQuestionnaireModal(
        coordinator=create_coordinator(),
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
    )

    options = modal.selection_group.options

    assert len(options) == 2

    defaults_by_value = {option.value: option.default for option in options}

    assert defaults_by_value == {
        "musicae": True,
        "codex": False,
    }


@pytest.mark.asyncio
async def test_member_modal_submits_selected_interest_keys() -> None:
    """Apply the exact interest keys submitted by the member."""

    coordinator = create_coordinator()

    coordinator.apply_selection.return_value = MemberRoleExecutionResult(
        added_role_ids=(20,),
        removed_role_ids=(10,),
    )

    modal = MemberQuestionnaireModal(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
    )

    interaction = create_interaction()

    with patch.object(
        CatalogSelectionModal,
        "selected_keys",
        new_callable=PropertyMock,
        return_value=("codex",),
    ):
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
        ("codex",),
    )

    assert interaction.edit_original_response.await_count == 2

    final_message = interaction.edit_original_response.await_args_list[-1].kwargs[
        "content"
    ]

    assert "2 modifications" in final_message


@pytest.mark.asyncio
async def test_member_modal_reports_apply_failure() -> None:
    """Allow the member to retry when role reconciliation fails."""

    coordinator = create_coordinator()

    coordinator.apply_selection.side_effect = RuntimeError(
        "Discord exploded.",
    )

    modal = MemberQuestionnaireModal(
        coordinator=coordinator,
        policy=SUCCUMBRAE_FALLBACK_POLICY,
        questionnaire=create_questionnaire(),
        actor_id=42,
    )

    interaction = create_interaction()

    with patch.object(
        CatalogSelectionModal,
        "selected_keys",
        new_callable=PropertyMock,
        return_value=("musicae",),
    ):
        await modal.on_submit(
            interaction,
        )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
        thinking=True,
    )

    coordinator.apply_selection.assert_awaited_once()

    final_message = interaction.edit_original_response.await_args_list[-1].kwargs[
        "content"
    ]

    assert "relancer `/membre`" in final_message
