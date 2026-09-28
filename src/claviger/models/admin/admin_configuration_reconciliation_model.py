from dataclasses import dataclass
from enum import StrEnum

from claviger.models.admin.admin_structure_discovery_model import (
    AdminCategoryCandidate,
)
from claviger.models.inspection import InspectionFinding


class AdminConfigurationReconciliationDecision(StrEnum):
    """Describe the next action required for administrative configuration."""

    KEEP = "keep"
    IMPORT = "import"
    COMPLETE = "complete"
    CREATE = "create"
    NEEDS_CHOICE = "needs_choice"


class AdminConfigurationFindingCode(StrEnum):
    """Stable machine-readable ADMIN reconciliation finding codes."""

    MULTIPLE_CATEGORIES = "admin.category.multiple_candidates"
    CONFIGURED_CATEGORY_MISSING = "admin.category.configured_missing"
    CATEGORY_PUBLIC = "admin.category.public"
    CATEGORY_APPLICATION_UNAVAILABLE = "admin.category.application_unavailable"
    TEXT_CHANNEL_MISSING = "admin.category.text_channel_missing"
    FORUM_COUNT_INSUFFICIENT = "admin.category.forum_count_insufficient"
    USABLE_TEXT_CHANNEL_MISSING = "admin.category.usable_text_channel_missing"
    USABLE_FORUM_COUNT_INSUFFICIENT = (
        "admin.category.usable_forum_count_insufficient"
    )
    CHANNEL_MISSING = "admin.channel.missing"
    CHANNEL_WRONG_TYPE = "admin.channel.wrong_type"
    CHANNEL_PUBLIC = "admin.channel.public"
    CHANNEL_APPLICATION_UNUSABLE = "admin.channel.application_unusable"
    COMMAND_CHANNEL_MISSING = "admin.routing.command_channel_missing"
    ERROR_FORUM_MISSING = "admin.routing.error_forum_missing"
    DESTINATIONS_COLLIDE = "admin.routing.destinations_collide"


@dataclass(frozen=True, slots=True)
class AdminConfigurationReconciliationResult:
    """Describe Discord/Admin reconciliation with structured findings."""

    decision: AdminConfigurationReconciliationDecision
    category: AdminCategoryCandidate | None
    findings: tuple[InspectionFinding, ...] = ()
