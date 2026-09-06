from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_questionnaire_model import (
    AdultAccessQuestionnaire,
)
from claviger.models.adult_access_theme_model import AdultAccessTheme
from claviger.policies.default_policy import (
    SUCCUMBRAE_FALLBACK_POLICY,
)
from claviger.services.role_discovery import RoleDiscoveryService
from claviger.ui.noctis_questionnaire_view import (
    NoctisQuestionnaireView,
)

from .helpers import (
    create_interaction,
    get_noctis_preview_command,
)


def create_questionnaire() -> AdultAccessQuestionnaire:
    """Create a minimal questionnaire for command tests."""

    base_access = AdultAccess(
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

    theme = AdultAccessTheme(
        theme_key="yuri",
        base_access=base_access,
        ai_access=None,
    )

    return AdultAccessQuestionnaire(
        themes=(theme,),
        selected_theme_keys=(),
        include_ai=False,
    )


@pytest.mark.asyncio
async def test_noctis_preview_opens_real_questionnaire_in_preview_mode() -> None:
    """Open the production questionnaire without enabling role mutations."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_noctis_preview_command(
        role_discovery_service,
    )

    questionnaire = create_questionnaire()

    coordinator.build_questionnaire.return_value = questionnaire

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

    assert view.preview is True


@pytest.mark.asyncio
async def test_noctis_preview_rejects_non_owner() -> None:
    """Restrict Noctis preview to the guild owner."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_noctis_preview_command(
        role_discovery_service,
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=99,
    )

    await command.callback(
        interaction,
    )

    database_status_service.check.assert_not_awaited()
    policy_resolver.resolve.assert_not_awaited()
    coordinator.build_questionnaire.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_preview_requires_ready_database() -> None:
    """Reject preview while the database requires migration."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        database_status_service,
        report_service,
    ) = get_noctis_preview_command(
        role_discovery_service,
    )

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

    database_status_service.check.assert_awaited_once()
    policy_resolver.resolve.assert_not_awaited()
    coordinator.build_questionnaire.assert_not_awaited()
    report_service.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_noctis_preview_reports_unexpected_failure() -> None:
    """Report failures while building the preview questionnaire."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    (
        command,
        coordinator,
        policy_resolver,
        _,
        report_service,
    ) = get_noctis_preview_command(
        role_discovery_service,
    )

    coordinator.build_questionnaire.side_effect = RuntimeError(
        "Questionnaire failed.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    policy_resolver.resolve.assert_awaited_once_with(
        123,
    )

    coordinator.build_questionnaire.assert_awaited_once()

    report_service.emit.assert_awaited_once()

    message = interaction.response.send_message.await_args.args[0]

    assert message == "Impossible de construire le questionnaire Noctis."
