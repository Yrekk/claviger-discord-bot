from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.noctis_admin_command import (
    create_noctis_admin_group,
)
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.ui.noctis_questionnaire_modal import (
    NoctisQuestionnaireModal,
)


def create_questionnaire() -> Mock:
    """Create a minimal questionnaire suitable for the modal preview."""

    theme = Mock()

    theme.theme_key = "yuri"
    theme.label = "Yuri"
    theme.description = "Contenus centrés sur des relations entre femmes."
    theme.emoji = "🌸"

    questionnaire = Mock()

    questionnaire.themes = (theme,)
    questionnaire.selected_theme_keys = ("yuri",)
    questionnaire.include_ai = False

    return questionnaire


def create_interaction(
    *,
    owner_id: int = 42,
    user_id: int = 42,
) -> Mock:
    """Create a mocked Discord interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123
    guild.name = "Succumbrae Atrium"
    guild.owner_id = owner_id

    user = Mock(
        spec=discord.Member,
    )
    user.id = user_id
    user.display_name = "Yrekk"

    interaction.guild = guild
    interaction.user = user

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()

    return interaction


def create_group():
    """Create the Noctis admin group with mocked dependencies."""

    coordinator = Mock()
    coordinator.build_questionnaire = AsyncMock(
        return_value=create_questionnaire(),
    )

    policy_resolver = Mock()
    policy_resolver.resolve = AsyncMock(
        return_value=SUCCUMBRAE_FALLBACK_POLICY,
    )

    database_status_service = Mock()
    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=4,
            target_version=4,
        )
    )

    report_service = Mock()
    report_service.emit = AsyncMock()

    group = create_noctis_admin_group(
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    )

    return (
        group,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    )


def get_preview_command(
    group,
):
    """Retrieve /claviger noctis preview."""

    command = group.get_command(
        "preview",
    )

    assert command is not None

    return command


@pytest.mark.asyncio
async def test_noctis_preview_opens_real_questionnaire_in_preview_mode() -> None:
    """Open the native Noctis checkbox modal in preview mode."""

    (
        group,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_group()

    interaction = create_interaction()

    command = get_preview_command(
        group,
    )

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
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    report_service.emit.assert_not_awaited()

    interaction.response.send_modal.assert_awaited_once()

    modal = interaction.response.send_modal.await_args.args[0]

    assert isinstance(
        modal,
        NoctisQuestionnaireModal,
    )

    assert modal.actor_id == interaction.user.id

    interaction.response.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_preview_rejects_non_owner() -> None:
    """Prevent non-owners from opening the Noctis preview."""

    (
        group,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_group()

    interaction = create_interaction(
        owner_id=1,
        user_id=42,
    )

    command = get_preview_command(
        group,
    )

    await command.callback(
        interaction,
    )

    coordinator.build_questionnaire.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    database_status_service.check.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "propriétaire" in message


@pytest.mark.asyncio
async def test_noctis_preview_requires_ready_database() -> None:
    """Require a ready database before opening the preview modal."""

    (
        group,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_group()

    database_status_service.check.return_value = DatabaseStatus(
        state=DatabaseState.MIGRATION_REQUIRED,
        current_version=3,
        target_version=4,
    )

    interaction = create_interaction()

    command = get_preview_command(
        group,
    )

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_not_awaited()
    coordinator.build_questionnaire.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "base de données doit être prête" in message


@pytest.mark.asyncio
async def test_noctis_preview_reports_unexpected_failure() -> None:
    """Report unexpected failures while building the preview modal."""

    (
        group,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_group()

    coordinator.build_questionnaire.side_effect = RuntimeError(
        "Questionnaire failed.",
    )

    interaction = create_interaction()

    command = get_preview_command(
        group,
    )

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        interaction.guild.id,
    )

    coordinator.build_questionnaire.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    event = report_service.emit.await_args.args[0]

    assert event.event_type == "noctis.preview.failed"
    assert event.details == "Questionnaire failed."
    assert event.guild_id == interaction.guild.id
    assert event.actor_id == interaction.user.id

    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "Impossible de construire" in message
