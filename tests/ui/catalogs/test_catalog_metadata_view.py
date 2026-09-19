from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.models.catalogs.catalog_administration_model import (
    CatalogMetadataCandidate,
)
from claviger.reporting.service import ReportService
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)
from claviger.ui.catalogs.catalog_metadata_view import CatalogMetadataModal

pytestmark = pytest.mark.asyncio


def _candidate(
    entry_key: str,
) -> CatalogMetadataCandidate:
    return CatalogMetadataCandidate(
        catalog_key="interest",
        catalog_display_name="Membre",
        entry_key=entry_key,
        label=None,
        description=None,
        emoji=None,
        target_role_names=(f"interest-{entry_key}",),
        target_channel_names=(f"test-{entry_key}",),
    )


async def test_metadata_modal_updates_only_metadata_and_offers_next() -> None:
    service = Mock(spec=CatalogAdministrationService)
    service.update_metadata = AsyncMock(
        return_value=_candidate(
            "second",
        )
    )
    report_service = Mock(spec=ReportService)
    report_service.emit = AsyncMock()

    modal = CatalogMetadataModal(
        service=service,
        report_service=report_service,
        candidate=_candidate(
            "first",
        ),
        actor_id=42,
        guild_id=123,
    )
    modal.label_input._value = "Premier"
    modal.description_input._value = "Description de test"
    modal.emoji_input._value = "🧪"

    interaction = Mock(spec=discord.Interaction)
    interaction.guild = Mock(spec=discord.Guild)
    interaction.guild.id = 123
    interaction.guild.name = "Laboratorium"
    interaction.user = Mock(spec=discord.Member)
    interaction.user.id = 42
    interaction.user.display_name = "Yrekk"
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()

    await modal.on_submit(
        interaction,
    )

    service.update_metadata.assert_awaited_once_with(
        guild_id=123,
        catalog_key="interest",
        entry_key="first",
        label="Premier",
        description="Description de test",
        emoji="🧪",
    )
    report_service.emit.assert_awaited_once()

    followup = interaction.followup.send.await_args
    assert "Entrée suivante à compléter" in followup.args[0]
    assert followup.kwargs["view"].candidate.entry_key == "second"
