from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import DatabaseState
from claviger.models.admin.admin_configuration_coordination_model import (
    AdminConfigurationCoordinationResult,
)
from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
)
from claviger.models.admin.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.models.runtime.application_runtime_state_model import (
    DatabaseOwnershipState,
)
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.ui.admin.admin_configuration_view import (
    AdminCategorySelectionView,
    AdminRoutingSelectionView,
)
from claviger.ui.workflows.workflow_configuration_view import (
    WorkflowConfigurationStartView,
)

from .helpers import (
    create_interaction,
    get_config_server_command,
)


def _role_discovery_service() -> Mock:
    """Create one unused role discovery dependency."""

    service = Mock(
        spec=RoleDiscoveryService,
    )

    service.get_hierarchy = AsyncMock()

    return service


def _configuration() -> GuildAdminConfiguration:
    """Create one complete deterministic ADMIN configuration."""

    return GuildAdminConfiguration(
        guild_id=123,
        category_id=100,
        command_channel_id=200,
        activity_forum_id=201,
        error_forum_id=202,
    )


def _channel(
    *,
    channel_id: int,
    name: str,
    channel_type: str,
) -> AdminChannelCandidate:
    """Create one usable private ADMIN channel candidate."""

    return AdminChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        channel_type=channel_type,
        everyone_can_view=False,
        bot_can_view=True,
        bot_can_send=True,
    )


def _category(
    *,
    category_id: int = 100,
    name: str = "Claviger Admin",
) -> AdminCategoryCandidate:
    """Create one structurally ready ADMIN category candidate."""

    return AdminCategoryCandidate(
        category_id=category_id,
        category_name=name,
        everyone_can_view=False,
        bot_can_view=True,
        has_public_child=False,
        channels=(
            _channel(
                channel_id=200,
                name="admin-commands",
                channel_type="text",
            ),
            _channel(
                channel_id=201,
                name="report-activity",
                channel_type="forum",
            ),
            _channel(
                channel_id=202,
                name="report-error",
                channel_type="forum",
            ),
        ),
    )


def _coordination_result(
    decision: AdminConfigurationReconciliationDecision,
    *,
    category: AdminCategoryCandidate | None = None,
    configuration_after: GuildAdminConfiguration | None = None,
    configuration_updated: bool = False,
    changed: bool = False,
) -> AdminConfigurationCoordinationResult:
    """Create one deterministic config-server backend result."""

    reconciliation = AdminConfigurationReconciliationResult(
        decision=decision,
        category=category,
    )

    provisioning = AdminStructureProvisioningResult(
        guild_id=123,
        decision=decision,
        category_id=(category.category_id if category is not None else 100),
        created_category=changed,
        configuration=configuration_after,
    )

    return AdminConfigurationCoordinationResult(
        guild_id=123,
        configuration_before=None,
        configuration_after=configuration_after,
        reconciliation=reconciliation,
        provisioning=provisioning,
        configuration_updated=configuration_updated,
    )


@pytest.mark.asyncio
async def test_config_server_requires_guild() -> None:
    """Reject config-server outside a Discord guild."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    interaction = create_interaction()
    interaction.guild = None

    await command.callback(
        interaction,
    )

    coordinator.configure.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande doit être utilisée sur un serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_config_server_requires_guild_owner() -> None:
    """Restrict structural server configuration to the guild owner."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    interaction = create_interaction(
        owner_id=42,
        user_id=84,
    )

    await command.callback(
        interaction,
    )

    coordinator.configure.assert_not_awaited()

    interaction.response.send_message.assert_awaited_once_with(
        "Cette commande est réservée au propriétaire du serveur.",
        ephemeral=True,
    )


@pytest.mark.asyncio
async def test_config_server_requires_ready_database() -> None:
    """Keep config-server visible but safe while database maintenance is required."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
        database_state=DatabaseState.MIGRATION_REQUIRED,
        database_ownership_bound=False,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.configure.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "/claviger database status" in message


@pytest.mark.asyncio
async def test_config_server_requires_database_ownership() -> None:
    """Never configure a guild through an unbound application database."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
        database_state=DatabaseState.READY,
        database_ownership_bound=False,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.configure.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "/claviger database bind" in message
    assert "/claviger restart" in message


@pytest.mark.asyncio
async def test_config_server_rejects_ownership_mismatch_without_bind_guidance() -> None:
    """Keep mismatch recovery fail-closed without suggesting database takeover."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
        database_state=DatabaseState.READY,
        database_ownership_bound=False,
        database_ownership_state=DatabaseOwnershipState.MISMATCH,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.configure.assert_not_awaited()

    message = interaction.response.send_message.await_args.args[0]

    assert "autre application Discord" in message
    assert "mode minimal" in message
    assert "database bind" not in message


@pytest.mark.asyncio
async def test_config_server_create_runs_current_guild_configuration() -> None:
    """Create ADMIN routing and continue directly into workflow configuration."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    coordinator.configure.return_value = _coordination_result(
        AdminConfigurationReconciliationDecision.CREATE,
        configuration_after=_configuration(),
        configuration_updated=True,
        changed=True,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    interaction.response.defer.assert_awaited_once_with(
        ephemeral=True,
    )

    coordinator.configure.assert_awaited_once_with(
        interaction.guild,
    )

    calls = interaction.followup.send.await_args_list

    assert len(calls) == 2

    admin_message = calls[0].args[0]

    assert "Configuration ADMIN créée avec succès" in admin_message
    assert "workflows" in admin_message
    assert "/claviger restart" not in admin_message

    workflow_message = calls[1].args[0]
    workflow_kwargs = calls[1].kwargs

    assert "Configuration des workflows" in workflow_message

    assert isinstance(
        workflow_kwargs["view"],
        WorkflowConfigurationStartView,
    )


@pytest.mark.asyncio
async def test_config_server_keep_reports_valid_configuration() -> None:
    """Continue to workflows when ADMIN was already persistently ready."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    coordinator.configure.return_value = _coordination_result(
        AdminConfigurationReconciliationDecision.KEEP,
        configuration_after=_configuration(),
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    calls = interaction.followup.send.await_args_list

    assert len(calls) == 2

    admin_message = calls[0].args[0]

    assert "Configuration ADMIN valide" in admin_message
    assert "Aucun changement" in admin_message

    workflow_message = calls[1].args[0]
    workflow_kwargs = calls[1].kwargs

    assert "Configuration des workflows" in workflow_message

    assert isinstance(
        workflow_kwargs["view"],
        WorkflowConfigurationStartView,
    )


@pytest.mark.asyncio
async def test_config_server_import_opens_explicit_routing_view() -> None:
    """Require explicit semantic routing for an existing ADMIN structure."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    category = _category()

    coordinator.configure.return_value = _coordination_result(
        AdminConfigurationReconciliationDecision.IMPORT,
        category=category,
    )
    coordinator.prepare_category.return_value = category

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    coordinator.prepare_category.assert_awaited_once_with(
        interaction.guild,
        category.category_id,
    )

    kwargs = interaction.followup.send.await_args.kwargs

    assert isinstance(
        kwargs["view"],
        AdminRoutingSelectionView,
    )

    message = interaction.followup.send.await_args.args[0]

    assert "ne déduit jamais" in message


@pytest.mark.asyncio
async def test_config_server_needs_choice_opens_category_selection() -> None:
    """Expose explicit category selection when discovery is ambiguous."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    first = _category()
    second = _category(
        category_id=999,
        name="Existing Admin",
    )

    coordinator.configure.return_value = _coordination_result(
        AdminConfigurationReconciliationDecision.NEEDS_CHOICE,
    )
    coordinator.discover_candidates.return_value = (
        first,
        second,
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    kwargs = interaction.followup.send.await_args.kwargs

    assert isinstance(
        kwargs["view"],
        AdminCategorySelectionView,
    )

    message = interaction.followup.send.await_args.args[0]

    assert "Choisis explicitement" in message


@pytest.mark.asyncio
async def test_config_server_reports_unexpected_failure() -> None:
    """Fail safely when ADMIN coordination raises unexpectedly."""

    command, coordinator = get_config_server_command(
        _role_discovery_service(),
    )

    coordinator.configure.side_effect = RuntimeError(
        "Provisioning exploded.",
    )

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    interaction.followup.send.assert_awaited_once_with(
        (
            "❌ La configuration ADMIN a échoué avant de devenir opérationnelle. "
            "Aucune déduction automatique supplémentaire n'a été faite."
        ),
        ephemeral=True,
    )
