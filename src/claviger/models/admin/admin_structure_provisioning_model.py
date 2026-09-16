from dataclasses import dataclass

from claviger.models.admin.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
)
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)


@dataclass(frozen=True, slots=True)
class AdminStructureProvisioningResult:
    """Describe one administrative Discord provisioning attempt."""

    guild_id: int
    decision: AdminConfigurationReconciliationDecision

    category_id: int | None

    created_category: bool = False
    created_channel_ids: tuple[int, ...] = ()

    category_permissions_repaired: bool = False
    repaired_channel_ids: tuple[int, ...] = ()

    configuration: GuildAdminConfiguration | None = None

    @property
    def changed(self) -> bool:
        """Return whether Discord structure or permissions were mutated."""

        return (
            self.created_category
            or bool(self.created_channel_ids)
            or self.category_permissions_repaired
            or bool(self.repaired_channel_ids)
        )
