from claviger.commands.admin.config_command import _format_workflow_lines
from claviger.database.status import DatabaseState, DatabaseStatus
from claviger.models.runtime.guild_configuration_inspection_model import (
    GuildConfigurationInspectionResult,
)
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition
from claviger.models.workflows.workflow_structure_discovery_model import (
    WorkflowCategoryCandidate,
    WorkflowStructureCandidate,
    WorkflowStructureDiscoveryResult,
    WorkflowTextChannelCandidate,
)


def _channel(
    channel_id: int,
    name: str,
    category_id: int,
    *,
    send_override: bool,
) -> WorkflowTextChannelCandidate:
    return WorkflowTextChannelCandidate(
        channel_id=channel_id,
        channel_name=name,
        category_id=category_id,
        everyone_can_view=True,
        everyone_can_send=send_override,
        bot_can_view=True,
        bot_can_send=True,
        everyone_send_override=send_override,
    )


def test_config_scan_lists_workflows_and_unconfigured_discovered_structures() -> None:
    """Show configured workflow names plus Discord structures still to configure."""

    configured_category = WorkflowCategoryCandidate(
        category_id=100,
        category_name="GAMING",
        everyone_can_view=True,
        bot_can_view=True,
    )
    extra_category = WorkflowCategoryCandidate(
        category_id=200,
        category_name="ADULT",
        everyone_can_view=False,
        bot_can_view=True,
    )

    configured_management = _channel(
        101,
        "gestion-gaming",
        100,
        send_override=False,
    )
    configured_execution = _channel(
        102,
        "gaming",
        100,
        send_override=True,
    )
    extra_management = _channel(
        201,
        "gestion-adult",
        200,
        send_override=False,
    )
    extra_execution = _channel(
        202,
        "adult",
        200,
        send_override=True,
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="gamer",
        command_name="gamer",
        command_description="Configure tes jeux.",
        title="Gamer",
        description=None,
        policy_key="gamer",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(102,),
        catalogs=(),
        category_id=100,
        management_channel_id=101,
        primary_role_id=300,
    )

    discovery = WorkflowStructureDiscoveryResult(
        categories=(
            configured_category,
            extra_category,
        ),
        text_channels=(
            configured_management,
            configured_execution,
            extra_management,
            extra_execution,
        ),
        manageable_roles=(),
        can_create_channels=True,
        can_create_roles=True,
        workflow_candidates=(
            WorkflowStructureCandidate(
                category=configured_category,
                protected_channels=(
                    configured_management,
                ),
                interactive_channels=(
                    configured_execution,
                ),
            ),
            WorkflowStructureCandidate(
                category=extra_category,
                protected_channels=(
                    extra_management,
                ),
                interactive_channels=(
                    extra_execution,
                ),
            ),
        ),
    )

    result = GuildConfigurationInspectionResult(
        guild_id=123,
        application_id=789,
        database_status=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=12,
            target_version=12,
        ),
        database_owner_application_id=789,
        admin=None,
        policy=None,
        metrics=None,
        workflows=(
            workflow,
        ),
        workflow_discovery=discovery,
    )

    lines = _format_workflow_lines(
        result,
    )
    message = "\n".join(
        lines,
    )

    assert "**Workflows configurés (1)**" in message
    assert "**Gamer** — /gamer" in message
    assert "Catégorie : GAMING" in message
    assert "=============" in message

    assert "**Structures Discord détectées mais non configurées (1)**" in message
    assert "Catégorie : ADULT" in message
    assert "Salons protégés : #gestion-adult" in message
    assert "Salons interactifs : #adult" in message
