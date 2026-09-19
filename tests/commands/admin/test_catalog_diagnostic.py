from unittest.mock import AsyncMock, Mock

import pytest

from claviger.commands.admin.catalog_command import create_catalog_group
from claviger.models.runtime.workflow_catalog_diagnostic_model import (
    CatalogMetadataIssue,
    GuildCatalogDiagnosticResult,
    WorkflowCatalogDiagnostic,
    WorkflowCatalogSectionDiagnostic,
)
from claviger.reporting.service import ReportService
from claviger.services.runtime.workflow_catalog_diagnostic_service import (
    WorkflowCatalogDiagnosticService,
)

from .helpers import create_interaction


@pytest.mark.asyncio
async def test_catalog_scan_separates_workflows_and_reports_questionnaire_gaps() -> None:
    """Render workflow structure and missing questionnaire metadata clearly."""

    diagnostic_service = Mock(spec=WorkflowCatalogDiagnosticService)
    diagnostic_service.inspect = AsyncMock(
        return_value=GuildCatalogDiagnosticResult(
            workflows=(
                WorkflowCatalogDiagnostic(
                    workflow_key="gamer",
                    title="Gamer",
                    command_name="gamer",
                    category_name="GAMING",
                    management_channel_name="gestion-gaming",
                    execution_channel_names=("gaming",),
                    primary_role_name="Gamer",
                    primary_role_explicit_channel_names=(
                        "discussion-gamer",
                    ),
                    ai_questionnaire_owner=True,
                    structure_issues=(),
                    catalogs=(
                        WorkflowCatalogSectionDiagnostic(
                            catalog_key="gamer",
                            display_name="Jeux",
                            role_prefix="gamer-",
                            detected_role_names=(
                                "gamer-rpg",
                                "gamer-strategie",
                            ),
                            linked_channel_names=(
                                "rpg",
                                "strategie",
                            ),
                            entry_count=2,
                            complete_entry_count=1,
                            incomplete_entries=(
                                CatalogMetadataIssue(
                                    entry_key="strategie",
                                    label=None,
                                    missing_fields=(
                                        "label",
                                        "description",
                                    ),
                                ),
                            ),
                            unsynced_role_names=(
                                "gamer-strategie",
                            ),
                            role_issues=(),
                        ),
                    ),
                ),
            ),
        )
    )

    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    group = create_catalog_group(
        diagnostic_service,
        report_service,
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
    report_service.emit.assert_not_awaited()

    message = interaction.followup.send.await_args_list[0].args[0]

    assert "=============" in message
    assert "**Workflow — Gamer**" in message
    assert "- Commande : /gamer" in message
    assert "- Catégorie : GAMING" in message
    assert "- Rôle principal : Gamer" in message
    assert "#discussion-gamer" in message
    assert "- Pattern : gamer-" in message
    assert "- Entrées metadata incomplètes : 1" in message
    assert "strategie : label, description manquant(s)" in message
