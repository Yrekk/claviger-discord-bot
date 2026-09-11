from dataclasses import dataclass
from enum import StrEnum

from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
)


class AdminConfigurationReconciliationDecision(StrEnum):
    """Describe the next action required for administrative configuration."""

    KEEP = "keep"
    IMPORT = "import"
    COMPLETE = "complete"
    CREATE = "create"
    NEEDS_CHOICE = "needs_choice"


@dataclass(frozen=True, slots=True)
class AdminConfigurationReconciliationResult:
    """Describe the result of comparing Discord and persisted admin state."""

    decision: AdminConfigurationReconciliationDecision

    category: AdminCategoryCandidate | None

    issues: tuple[str, ...] = ()
