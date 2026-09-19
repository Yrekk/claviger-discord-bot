from unittest.mock import AsyncMock, Mock

import pytest

from claviger.commands.admin.catalog_command import (
    _format_catalog_diagnostic,
    create_catalog_group,
)
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
async def test_catalog_scan_separates_workflows_and_reports_gaps() -> None:
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
    assert "- Structure : ✅ VALIDE" in message
    assert "- Commande : ✅ /gamer configurée" in message
    assert "- Catégorie : GAMING" in message
    assert "- Rôle principal : Gamer" in message
    assert "#discussion-gamer" in message
    assert (
        "- État catalogue : ⚠️ MÉTADONNÉES INCOMPLÈTES "
        "+ SYNCHRONISATION REQUISE"
    ) in message
    assert "- Pattern : gamer-" in message
    assert "**⚠️ Problèmes détectés**" in message
    assert "strategie : label, description manquant(s)" in message
    assert "Synchronisation BDD requise pour : gamer-strategie" in message
    assert "**Résumé catalogue**" in message
    assert "- Métadonnées questionnaire complètes : 1 / 2" in message


def test_catalog_scan_formats_structure_errors_separately() -> None:
    """Keep workflow structure failures distinct from catalog readiness."""

    result = GuildCatalogDiagnosticResult(
        workflows=(
            WorkflowCatalogDiagnostic(
                workflow_key="adult",
                title="adult",
                command_name="adult",
                category_name="ADULT",
                management_channel_name=None,
                execution_channel_names=(),
                primary_role_name="adult",
                primary_role_explicit_channel_names=(),
                ai_questionnaire_owner=False,
                structure_issues=(
                    "salon de gestion absent de Discord",
                    "aucun salon d'exécution configuré",
                ),
                catalogs=(
                    WorkflowCatalogSectionDiagnostic(
                        catalog_key="adult",
                        display_name="adult",
                        role_prefix="access-",
                        detected_role_names=("access-test",),
                        linked_channel_names=("test-access",),
                        entry_count=1,
                        complete_entry_count=1,
                        incomplete_entries=(),
                        unsynced_role_names=(),
                        role_issues=(),
                    ),
                ),
            ),
        ),
    )

    message = "\n".join(
        _format_catalog_diagnostic(
            result,
        )
    )

    assert "- Structure : ❌ À CORRIGER" in message
    assert "**⚠️ Problèmes de structure**" in message
    assert "- salon de gestion absent de Discord" in message
    assert "- aucun salon d'exécution configuré" in message
    assert "- État catalogue : ✅ READY" in message
