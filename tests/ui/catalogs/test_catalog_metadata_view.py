from unittest.mock import Mock

from claviger.models.catalogs.catalog_administration_model import (
    CatalogMetadataCandidate,
)
from claviger.reporting.service import ReportService
from claviger.services.catalogs.catalog_administration_service import (
    CatalogAdministrationService,
)
from claviger.ui.catalogs.catalog_metadata_view import CatalogMetadataModal


def test_metadata_modal_prefills_candidate_without_touching_targets() -> None:
    """Expose human fields while keeping technical target identity read-only."""

    candidate = CatalogMetadataCandidate(
        catalog_key="interest",
        catalog_display_name="Membre",
        entry_key="test",
        label=None,
        description=None,
        emoji=None,
        target_role_names=("interest-test",),
        target_channel_names=("test-interest",),
    )

    modal = CatalogMetadataModal(
        service=Mock(spec=CatalogAdministrationService),
        report_service=Mock(spec=ReportService),
        candidate=candidate,
        actor_id=42,
        guild_id=123,
    )

    assert modal.candidate == candidate
    assert modal.label_input.default == "test"
    assert modal.description_input.default == ""
    assert modal.emoji_input.default == ""
    assert modal.label_input.required is True
    assert modal.description_input.required is True
    assert modal.emoji_input.required is False
