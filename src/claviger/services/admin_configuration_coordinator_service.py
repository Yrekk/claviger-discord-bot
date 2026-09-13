import discord

from claviger.models.admin_configuration_coordination_model import (
    AdminConfigurationCoordinationResult,
)
from claviger.repositories.guild_admin_configuration_repository import (
    GuildAdminConfigurationRepository,
)
from claviger.services.admin_configuration_reconciliation_service import (
    AdminConfigurationReconciliationService,
)
from claviger.services.admin_structure_discovery_service import (
    AdminStructureDiscoveryService,
)
from claviger.services.admin_structure_provisioning_service import (
    AdminStructureProvisioningService,
)


class AdminConfigurationCoordinatorService:
    """Coordinate one guild's persisted ADMIN configuration with Discord."""

    def __init__(
        self,
        *,
        repository: GuildAdminConfigurationRepository,
        discovery_service: AdminStructureDiscoveryService,
        reconciliation_service: AdminConfigurationReconciliationService,
        provisioning_service: AdminStructureProvisioningService,
    ) -> None:
        self.repository = repository
        self.discovery_service = discovery_service
        self.reconciliation_service = reconciliation_service
        self.provisioning_service = provisioning_service

    async def configure(
        self,
        guild: discord.Guild,
    ) -> AdminConfigurationCoordinationResult:
        """Run one DB-backed ADMIN discovery, reconciliation and provisioning pass."""

        configuration_before = await self.repository.get(
            guild.id,
        )

        discovery = self.discovery_service.discover(
            guild,
            configured_category_id=(
                configuration_before.category_id
                if configuration_before is not None
                else None
            ),
        )

        reconciliation = self.reconciliation_service.reconcile(
            discovery=discovery,
            configuration=configuration_before,
        )

        provisioning = await self.provisioning_service.provision(
            guild=guild,
            reconciliation=reconciliation,
            configuration=configuration_before,
        )

        configuration_after = configuration_before
        configuration_updated = False

        if (
            provisioning.configuration is not None
            and provisioning.configuration != configuration_before
        ):
            await self.repository.save(
                provisioning.configuration,
            )

            configuration_after = provisioning.configuration
            configuration_updated = True

        return AdminConfigurationCoordinationResult(
            guild_id=guild.id,
            configuration_before=configuration_before,
            configuration_after=configuration_after,
            reconciliation=reconciliation,
            provisioning=provisioning,
            configuration_updated=configuration_updated,
        )
