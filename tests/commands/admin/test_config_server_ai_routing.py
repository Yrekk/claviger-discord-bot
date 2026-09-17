from unittest.mock import AsyncMock, Mock

import pytest

from claviger.models.admin.admin_configuration_coordination_model import (
    AdminConfigurationCoordinationResult,
)
from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.models.runtime.guild_ai_configuration_model import (
    GuildAIConfiguration,
    GuildAIConfigurationInspection,
    GuildAIConfigurationInspectionState,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.guild_ai_configuration_coordinator_service import (
    GuildAIConfigurationCoordinatorService,
)
from claviger.ui.admin.guild_ai_configuration_view import (
    GuildAIConfigurationChoiceView,
)
from claviger.ui.workflows.workflow_configuration_view import (
    WorkflowConfigurationStartView,
)

from .helpers import create_interaction, get_config_server_command


def _role_discovery_service() -> Mock:
    """Create one unused role discovery dependency."""

    service = Mock(spec=RoleDiscoveryService)
    service.get_hierarchy = AsyncMock()
    return service


def _admin_ready_result() -> AdminConfigurationCoordinationResult:
    """Create one already-complete ADMIN coordination result."""

    configuration = GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )

    return AdminConfigurationCoordinationResult(
        guild_id=123,
        configuration_before=configuration,
        configuration_after=configuration,
        reconciliation=AdminConfigurationReconciliationResult(
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category=None,
        ),
        provisioning=AdminStructureProvisioningResult(
            guild_id=123,
            decision=AdminConfigurationReconciliationDecision.KEEP,
            category_id=100,
            configuration=configuration,
        ),
        configuration_updated=False,
    )


def _ai_coordinator(
    state: GuildAIConfigurationInspectionState,
) -> Mock:
    """Create one AI coordinator exposing the requested config-server state."""

    coordinator = Mock(spec=GuildAIConfigurationCoordinatorService)
    coordinator.inspect = AsyncMock(
        return_value=GuildAIConfigurationInspection(
            guild_id=123,
            state=state,
            configuration=GuildAIConfiguration(
                guild_id=123,
                ai_enabled=(
                    None
                    if state == GuildAIConfigurationInspectionState.UNCONFIGURED
                    else False
                ),
                ai_role_id=None,
            ),
        )
    )
    coordinator.enable = AsyncMock()
    coordinator.disable = AsyncMock()
    coordinator.assign_role = AsyncMock()
    coordinator.create_and_assign_role = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_config_server_stops_before_workflows_when_ai_is_unconfigured() -> None:
    """Insert the explicit guild AI decision between ADMIN and workflow setup."""

    ai_coordinator = _ai_coordinator(
        GuildAIConfigurationInspectionState.UNCONFIGURED,
    )
    command, admin_coordinator = get_config_server_command(
        _role_discovery_service(),
        ai_configuration_coordinator_service=ai_coordinator,
    )
    admin_coordinator.configure.return_value = _admin_ready_result()
    interaction = create_interaction()

    await command.callback(interaction)

    ai_coordinator.inspect.assert_awaited_once_with(interaction.guild)

    calls = interaction.followup.send.await_args_list
    assert len(calls) == 2
    assert "Configuration ADMIN valide" in calls[0].args[0]
    assert "Configuration IA du serveur" in calls[1].args[0]
    assert isinstance(calls[1].kwargs["view"], GuildAIConfigurationChoiceView)
    assert not any(
        isinstance(call.kwargs.get("view"), WorkflowConfigurationStartView)
        for call in calls
    )


@pytest.mark.asyncio
async def test_config_server_continues_when_ai_is_explicitly_disabled() -> None:
    """Treat the explicit guild opt-out as sufficient readiness for workflows."""

    ai_coordinator = _ai_coordinator(
        GuildAIConfigurationInspectionState.DISABLED,
    )
    command, admin_coordinator = get_config_server_command(
        _role_discovery_service(),
        ai_configuration_coordinator_service=ai_coordinator,
    )
    admin_coordinator.configure.return_value = _admin_ready_result()
    interaction = create_interaction()

    await command.callback(interaction)

    calls = interaction.followup.send.await_args_list
    assert len(calls) == 2
    assert isinstance(calls[1].kwargs["view"], WorkflowConfigurationStartView)
