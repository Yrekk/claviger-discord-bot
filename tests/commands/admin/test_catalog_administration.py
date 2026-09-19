from unittest.mock import AsyncMock, Mock

import pytest

from claviger.commands.admin.catalog_command import create_catalog_group
from claviger.models.catalogs.catalog_administration_model import (
    CatalogMetadataCandidate,
    CatalogSynchronizationSummary,
)
from claviger.reporting.service import ReportService
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)
from claviger.services.runtime.workflow_catalog_diagnostic_service import (
    WorkflowCatalogDiagnosticService,
)

from .helpers import create_interaction

pytestmark = pytest.mark.asyncio


def _services():
    diagnostic_service = Mock(spec=WorkflowCatalogDiagnosticService)
    administration_service = Mock(spec=CatalogAdministrationService)
    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    group = create_catalog_group(
        diagnostic_service,
        report_service,
        administration_service=administration_service,
    )

    return group, administration_service, report_service


async def test_catalog_sync_uses_generic_administration_service() -> None:
    group, administration_service, report_service = _services()
    administration_service.synchronize_all = AsyncMock(
        return_value=(
            CatalogSynchronizationSummary(
                catalog_key="interest",
                display_name="Membre",
                role_prefix="interest-",
                entry_count=1,
                incomplete_metadata_count=1,
            ),
        )
    )

    command = group.get_command(
        "sync",
    )
    assert command is not None

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    administration_service.synchronize_all.assert_awaited_once_with(
        interaction.guild,
    )
    report_service.emit.assert_awaited_once()

    message = interaction.followup.send.await_args_list[-1].args[0]
    assert "**Synchronisation des catalogues**" in message
    assert "**Membre** — pattern `interest-`" in message
    assert "- ✅ Entrées techniques : 1" in message
    assert "- Métadonnées incomplètes : 1" in message


async def test_catalog_next_opens_metadata_modal() -> None:
    group, administration_service, _ = _services()
    administration_service.next_incomplete = AsyncMock(
        return_value=CatalogMetadataCandidate(
            catalog_key="interest",
            catalog_display_name="Membre",
            entry_key="test",
            label=None,
            description=None,
            emoji=None,
            target_role_names=("interest-test",),
            target_channel_names=("test-interest",),
        )
    )

    command = group.get_command(
        "next",
    )
    assert command is not None

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    administration_service.next_incomplete.assert_awaited_once_with(
        interaction.guild.id,
    )
    interaction.response.send_modal.assert_awaited_once()

    modal = interaction.response.send_modal.await_args.args[0]
    assert modal.candidate.entry_key == "test"
    assert str(modal.label_input.default) == "test"


async def test_catalog_next_reports_when_everything_is_complete() -> None:
    group, administration_service, _ = _services()
    administration_service.next_incomplete = AsyncMock(
        return_value=None,
    )

    command = group.get_command(
        "next",
    )
    assert command is not None

    interaction = create_interaction()

    await command.callback(
        interaction,
    )

    interaction.response.send_modal.assert_not_awaited()
    interaction.response.send_message.assert_awaited_once()
    assert "Toutes les entrées actives" in (
        interaction.response.send_message.await_args.args[0]
    )
