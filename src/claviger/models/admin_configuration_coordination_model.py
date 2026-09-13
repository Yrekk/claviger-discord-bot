from dataclasses import dataclass

from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin_structure_provisioning_model import (
    AdminStructureProvisioningResult,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


@dataclass(frozen=True, slots=True)
class AdminConfigurationCoordinationResult:
    """Describe one complete DB-backed ADMIN configuration pass."""

    guild_id: int

    configuration_before: GuildAdminConfiguration | None
    configuration_after: GuildAdminConfiguration | None

    reconciliation: AdminConfigurationReconciliationResult
    provisioning: AdminStructureProvisioningResult

    configuration_updated: bool
