from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.commands.noctis_command import create_noctis_command
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
    DatabaseStatusService,
)
from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import (
    AdultAccessTheme,
)
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.policies.policy_resolver import PolicyResolver
from claviger.reporting.service import ReportService
from claviger.services.noctis_workflow_coordinator_service import (
    NoctisWorkflowCoordinatorService,
)
from claviger.ui.noctis_questionnaire_view import (
    NoctisQuestionnaireView,
)


def create_questionnaire() -> AdultAccessQuestionnaire:
    """Create one available Noctis theme."""

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
        selected_theme_keys=(),
        include_ai=False,
    )


def create_interaction(
    *,
    channel_name: str = "lex-noctis",
) -> Mock:
    """Create a mocked guild interaction."""

    interaction = Mock(
        spec=discord.Interaction,
    )

    guild = Mock(
        spec=discord.Guild,
    )
    guild.id = 123
    guild.name = "Succumbrae Atrium"

    member = Mock(
        spec=discord.Member,
    )
    member.id = 42
    member.display_name = "Yrekk"

    channel = Mock(
        spec=discord.TextChannel,
    )
    channel.name = channel_name

    interaction.guild = guild
    interaction.user = member
    interaction.channel = channel

    interaction.response = Mock()
    interaction.response.send_message = AsyncMock()

    return interaction


def create_command(
    *,
    policy=SUCCUMBRAE_FALLBACK_POLICY,
):
    """Create /noctis with mocked dependencies."""

    coordinator = Mock(
        spec=NoctisWorkflowCoordinatorService,
    )
    coordinator.build_questionnaire = AsyncMock(
        return_value=create_questionnaire(),
    )

    policy_resolver = Mock(
        spec=PolicyResolver,
    )
    policy_resolver.resolve = AsyncMock(
        return_value=policy,
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

    report_service = Mock(
        spec=ReportService,
    )
    report_service.emit = AsyncMock()

    command = create_noctis_command(
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    )

    return (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    )


@pytest.mark.asyncio
async def test_noctis_opens_live_questionnaire_in_rules_channel() -> None:
    """Open the production questionnaire in the configured rules channel."""

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_command()

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_awaited_once()

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.build_questionnaire.assert_awaited_once_with(
        interaction.guild,
        interaction.user,
        SUCCUMBRAE_FALLBACK_POLICY,
    )

    report_service.emit.assert_not_awaited()

    kwargs = interaction.response.send_message.await_args.kwargs

    view = kwargs["view"]

    assert isinstance(
        view,
        NoctisQuestionnaireView,
    )

    assert view.preview is False
    assert kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_noctis_rejects_wrong_channel() -> None:
    """Restrict /noctis to the configured adult-rules channel."""

    (
        command,
        coordinator,
        _,
        _,
        report_service,
    ) = create_command()

    interaction = create_interaction(
        channel_name="general",
    )

    await command.callback(
        interaction,
    )

    coordinator.build_questionnaire.assert_not_awaited()
    report_service.emit.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "lex-noctis" in message


@pytest.mark.asyncio
async def test_noctis_requires_ready_database() -> None:
    """Reject the workflow when the database is not ready."""

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = create_command()

    database_status_service.check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.MIGRATION_REQUIRED,
            current_version=2,
            target_version=4,
        )
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.build_questionnaire.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_rejects_disabled_adult_workflow() -> None:
    """Reject /noctis when adult access is disabled by policy."""

    disabled_policy = replace(
        SUCCUMBRAE_FALLBACK_POLICY,
        adult_access_enabled=False,
    )

    (
        command,
        coordinator,
        _,
        _,
        report_service,
    ) = create_command(
        policy=disabled_policy,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.build_questionnaire.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_reports_empty_catalog() -> None:
    """Report that no public adult-access themes are available."""

    (
        command,
        coordinator,
        _,
        _,
        report_service,
    ) = create_command()

    coordinator.build_questionnaire.return_value = AdultAccessQuestionnaire(
        themes=(),
        selected_theme_keys=(),
        include_ai=False,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    message = interaction.response.send_message.await_args.args[0]

    assert "Aucun accès adulte" in message
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_reports_unexpected_failure() -> None:
    """Report unexpected failures while opening /noctis."""

    (
        command,
        coordinator,
        _,
        _,
        report_service,
    ) = create_command()

    coordinator.build_questionnaire.side_effect = RuntimeError(
        "Questionnaire failed.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    report_service.emit.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert "incident a été signalé" in message
