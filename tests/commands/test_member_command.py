from dataclasses import replace
from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from claviger.commands.member_command import (
    create_member_command,
)
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.models.member_interest_questionnaire_model import (
    MemberInterestQuestionnaire,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.services.member_workflow_coordinator_service import (
    MemberWorkflowCoordinatorService,
)


def create_interaction(
    *,
    guild_id: int = 123,
    channel_name: str = "salutations",
    user_id: int = 42,
) -> Mock:
    """Create a mocked Discord interaction for /membre tests."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = guild_id

    member = Mock(
        spec=discord.Member,
    )
    member.id = user_id

    channel = Mock(
        spec=discord.TextChannel,
    )
    channel.name = channel_name

    interaction.guild = guild
    interaction.user = member
    interaction.channel = channel

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()

    return interaction


def create_command():
    """Create /membre with mocked dependencies."""

    policy_resolver = Mock(
        spec=PolicyResolver,
    )
    policy_resolver.resolve = AsyncMock(
        return_value=SUCCUMBRAE_FALLBACK_POLICY,
    )

    database_status_service = Mock(
        spec=DatabaseStatusService,
    )
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=4,
            target_version=4,
        )
    )

    coordinator = Mock(
        spec=MemberWorkflowCoordinatorService,
    )
    coordinator.build_questionnaire = AsyncMock(
        return_value=MemberInterestQuestionnaire(
            interests=(),
            selected_interest_keys=(),
        )
    )

    command = create_member_command(
        policy_resolver=policy_resolver,
        database_status_service=database_status_service,
        member_workflow_coordinator_service=coordinator,
    )

    return (
        command,
        policy_resolver,
        database_status_service,
        coordinator,
    )


@pytest.mark.asyncio
async def test_member_command_rejects_interaction_outside_guild() -> None:
    """Reject /membre outside a Discord guild."""

    (
        command,
        policy_resolver,
        database_status_service,
        coordinator,
    ) = create_command()

    interaction = create_interaction()
    interaction.guild = None

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    coordinator.build_questionnaire.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_member_command_requires_ready_database() -> None:
    """Reject /membre while Claviger's database is not ready."""

    (
        command,
        policy_resolver,
        database_status_service,
        coordinator,
    ) = create_command()

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.MISSING,
        current_version=None,
        target_version=4,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_not_awaited()
    coordinator.build_questionnaire.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "base de données" in message
    assert "pas prête" in message


@pytest.mark.asyncio
async def test_member_command_rejects_disabled_role_management() -> None:
    """Respect the effective guild role-management policy."""

    (
        command,
        policy_resolver,
        database_status_service,
        coordinator,
    ) = create_command()

    policy = replace(
        SUCCUMBRAE_FALLBACK_POLICY,
        role_management_enabled=False,
    )

    policy_resolver.resolve.return_value = policy

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        interaction.guild.id,
    )

    coordinator.build_questionnaire.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "La gestion des rôles membre est désactivée sur ce serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_member_command_requires_salutations_channel() -> None:
    """Expose /membre only in the configured salutations channel."""

    (
        command,
        policy_resolver,
        _,
        coordinator,
    ) = create_command()

    interaction = create_interaction(
        channel_name="general",
    )

    await command.callback(
        interaction,
    )

    policy_resolver.resolve.assert_awaited_once_with(
        interaction.guild.id,
    )

    coordinator.build_questionnaire.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée dans `#salutationes`.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_member_command_opens_questionnaire_in_policy_channel() -> None:
    """Build and open the questionnaire using the effective guild policy."""

    (
        command,
        policy_resolver,
        database_status_service,
        coordinator,
    ) = create_command()

    policy = replace(
        SUCCUMBRAE_FALLBACK_POLICY,
        salutations_channel_name="atrium",
    )

    policy_resolver.resolve.return_value = policy

    questionnaire = MemberInterestQuestionnaire(
        interests=(),
        selected_interest_keys=(),
    )

    coordinator.build_questionnaire.return_value = questionnaire

    interaction = create_interaction(
        channel_name="atrium",
    )

    with patch(
        "claviger.commands.member_command.MemberQuestionnaireModal",
    ) as modal_class:
        modal = Mock()
        modal_class.return_value = modal

        await command.callback(
            interaction,
        )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        interaction.guild.id,
    )

    coordinator.build_questionnaire.assert_awaited_once_with(
        interaction.guild,
        interaction.user,
        policy,
    )

    modal_class.assert_called_once_with(
        coordinator=coordinator,
        policy=policy,
        questionnaire=questionnaire,
        actor_id=interaction.user.id,
    )

    interaction.response.send_modal.assert_awaited_once_with(
        modal,
    )

    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_member_command_reports_questionnaire_failure() -> None:
    """Return a safe response when questionnaire preparation fails."""

    (
        command,
        _,
        _,
        coordinator,
    ) = create_command()

    coordinator.build_questionnaire.side_effect = RuntimeError(
        "Catalog exploded.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.build_questionnaire.assert_awaited_once()

    interaction.response.send_modal.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        (
            "Impossible de préparer le questionnaire membre. "
            "Réessaie dans quelques instants."
        ),
        ephemeral=True,
    )
