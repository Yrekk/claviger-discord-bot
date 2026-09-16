from dataclasses import dataclass

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
    AdminConfigurationReconciliationResult,
)
from claviger.models.admin.admin_structure_discovery_model import (
    AdminStructureDiscoveryResult,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


@dataclass(frozen=True, slots=True)
class AdminConfigurationInspectionResult:
    """Describe persisted ADMIN routing compared with current Discord state."""

    guild_id: int
    configuration: GuildAdminConfiguration | None
    discovery: AdminStructureDiscoveryResult
    reconciliation: AdminConfigurationReconciliationResult

    @property
    def is_routing_ready(self) -> bool:
        """Return whether persisted ADMIN routing is complete and still usable."""

        return (
            self.configuration is not None
            and self.configuration.is_complete
            and self.reconciliation.decision
            == AdminConfigurationReconciliationDecision.KEEP
        )

    @property
    def command_channel_id(self) -> int | None:
        """Return the authoritative ADMIN command channel when routing is ready."""

        if not self.is_routing_ready or self.configuration is None:
            return None

        return self.configuration.command_channel_id
