from unittest.mock import AsyncMock, Mock

import pytest

from claviger.commands.config_command import create_config_group
from claviger.database.status import DatabaseState, DatabaseStatus
from claviger.models.admin_configuration_inspection_model import (
    AdminConfigurationInspectionResult,
)
from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminStructureDiscoveryResult,
)
from claviger.models.guild_admin_configuration_model import GuildAdminConfiguration
from claviger.models.guild_configuration_inspection_model import (
    GuildConfigurationInspectionResult,
)
from claviger.models.guild_configuration_metrics_model import GuildConfigurationMetrics
from claviger.models.guild_policy_inspection_model import (
    GuildPolicyInspection,
    GuildPolicySource,
)
from claviger.policies.default_policy import SAFE_DEFAULT_POLICY
from claviger.reporting.service import ReportService
from claviger.services.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)

from .helpers import create_interaction


def _create_ready_result() -> GuildConfigurationInspectionResult:
    command_channel = AdminChannelCandidate(
        channel_id=1001,
        channel_name="admin-commands",
        channel_type="text",
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )
    activity_forum = AdminChannelCandidate(
        channel_id=1002,
        channel_name="report-activity",
        channel_type="forum",
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )
    error_forum = AdminChannelCandidate(
        channel_id=1003,
        channel_name="report-error",
        channel_type="forum",
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )

    category = AdminCategoryCandidate(
        category_id=1000,
        category_name="ADMIN",
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(command_channel, activity_forum, error_forum),
    )

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=1000,
        command_channel_id=1001,
        activity_forum_id=1002,
        error_forum_id=1003,
    )

    admin = AdminConfigurationInspectionResult(
        guild_id=123,
        configuration=configuration,
        discovery=AdminStructureDiscoveryResult(
            categories=(category,),
        ),
        reconciliation=AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category=category,
        ),
    )

    return GuildConfigurationInspectionResult(
        guild_id=123,
        application_id=789,
        database_status=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=10,
            target_version=10,
        ),
        database_owner_application_id=789,
        admin=admin,
        policy=GuildPolicyInspection(
            effective=SAFE_DEFAULT_POLICY,
            source=GuildPolicySource.SAFE_DEFAULT,
        ),
        metrics=GuildConfigurationMetrics(
            workflow_count=2,
            catalog_count=3,
            context_count=1,
        ),
    )


@pytest.mark.asyncio
async def test_config_scan_displays_live_admin_health_and_generic_counts() -> None:
    inspection_service = Mock(spec=GuildConfigurationInspectionService)
    inspection_service.inspect = AsyncMock(
        return_value=_create_ready_result(),
    )

    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    group = create_config_group(
        inspection_service,
        report_service,
        application_name="Experimentum",
        application_id=789,
    )

    command = group.get_command("scan")
    assert command is not None

    interaction = create_interaction(
        guild_id=123,
        guild_name="Laboratium",
    )

    await command.callback(
        interaction,
    )

    message = interaction.followup.send.await_args.args[0]

    assert "**Application — Experimentum**" in message
    assert "- Persistance BDD : ✅ complète" in message
    assert "#admin-commands" in message
    assert "#report-activity" in message
    assert "#report-error" in message
    assert "- État : ✅ READY" in message
    assert "- Source : `SAFE_DEFAULT_POLICY`" in message
    assert "- Workflows activés : 2" in message
    assert "- Catalogues activés : 3" in message
    assert "- Contextes partagés activés : 1" in message

    report_service.emit.assert_not_awaited()
