from unittest.mock import AsyncMock, Mock

import pytest

from claviger.commands.admin.roles import create_roles_group
from claviger.models.runtime.guild_role_diagnostic_model import (
    GuildRoleDiagnosticResult,
    RolePatternAnomaly,
)
from claviger.reporting.service import ReportService
from claviger.services.roles.role_discovery import RoleDiscoveryService
from claviger.services.runtime.guild_role_diagnostic_service import (
    GuildRoleDiagnosticService,
)

from .helpers import create_interaction


@pytest.mark.asyncio
async def test_roles_scan_uses_workflow_aware_diagnostic_without_ids() -> None:
    """Separate special, anomalous and unrelated roles for human diagnostics."""

    role_discovery = Mock(spec=RoleDiscoveryService)
    role_discovery.get_hierarchy = AsyncMock()

    diagnostic_service = Mock(spec=GuildRoleDiagnosticService)
    diagnostic_service.inspect = AsyncMock(
        return_value=GuildRoleDiagnosticResult(
            bot_role_name="Experimentum",
            ai_enabled=True,
            ai_role_name="IA",
            ai_role_missing=False,
            workflow_primary_role_names=(
                "Gamer",
            ),
            configured_catalog_role_names=(
                "gamer-rpg",
            ),
            unconfigured_manageable_role_names=(
                "Autre rôle",
            ),
            unmanageable_role_names=(
                "Integration",
            ),
            pattern_anomalies=(
                RolePatternAnomaly(
                    role_name="gamer-anomalie",
                    workflow_labels=(
                        "Gamer / Jeux",
                    ),
                    channel_names=(),
                    reasons=(
                        "aucun salon/forum avec visibilité explicite",
                        "absent des targets catalogue en BDD",
                    ),
                ),
            ),
        )
    )

    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    group = create_roles_group(
        role_discovery,
        report_service,
        diagnostic_service=diagnostic_service,
    )
    command = group.get_command(
        "scan",
    )
    assert command is not None

    interaction = create_interaction(
        guild_id=123,
    )

    await command.callback(
        interaction,
    )

    diagnostic_service.inspect.assert_awaited_once_with(
        interaction.guild,
    )
    role_discovery.get_hierarchy.assert_not_awaited()

    message = interaction.followup.send.await_args_list[0].args[0]

    assert "- Rôle de l'application : Experimentum" in message
    assert "- Rôle IA : IA" in message
    assert "**Rôles principaux de workflow (1)**" in message
    assert "- Gamer" in message
    assert "**Anomalies de pattern (1)**" in message
    assert "gamer-anomalie" in message
    assert "**Rôles manipulables hors workflows (1)**" in message
    assert "- Autre rôle" in message
    assert "**Rôles non manipulables (1)**" in message
    assert "123456789" not in message
