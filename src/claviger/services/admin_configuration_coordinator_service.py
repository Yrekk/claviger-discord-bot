import discord

from claviger.models.admin_configuration_coordination_model import (
    AdminConfigurationCoordinationResult,
)
from claviger.models.admin_configuration_reconciliation_model import (
    AdminConfigurationReconciliationDecision,
)
from claviger.models.admin_structure_discovery_model import (
    AdminCategoryCandidate,
    AdminChannelCandidate,
    AdminStructureDiscoveryResult,
)
from claviger.models.guild_admin_configuration_model import (
    GuildAdminConfiguration,
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

    async def get_persisted_configuration(
        self,
        guild_id: int,
    ) -> GuildAdminConfiguration | None:
        """Return one guild's persisted ADMIN routing without Discord mutation."""

        return await self.repository.get(
            guild_id,
        )

    async def discover_candidates(
        self,
        guild: discord.Guild,
    ) -> tuple[AdminCategoryCandidate, ...]:
        """Return current ADMIN category candidates without mutating Discord."""

        configuration = await self.repository.get(
            guild.id,
        )

        discovery = self.discovery_service.discover(
            guild,
            configured_category_id=(
                configuration.category_id if configuration is not None else None
            ),
        )

        return discovery.categories

    async def prepare_category(
        self,
        guild: discord.Guild,
        category_id: int,
    ) -> AdminCategoryCandidate:
        """Prepare one explicitly selected ADMIN category for semantic routing.

        The category identity has already been chosen by a human. Claviger may
        therefore perform only the safe structural repairs already supported by
        the provisioning service, then rediscover the category before exposing
        routing choices.
        """

        if category_id <= 0:
            raise ValueError("ADMIN category ID must be greater than zero.")

        category = self._discover_selected_category(
            guild,
            category_id=category_id,
        )

        selected_discovery = AdminStructureDiscoveryResult(
            categories=(category,),
        )

        reconciliation = self.reconciliation_service.reconcile(
            discovery=selected_discovery,
            configuration=None,
        )

        if reconciliation.decision == AdminConfigurationReconciliationDecision.COMPLETE:
            await self.provisioning_service.provision(
                guild=guild,
                reconciliation=reconciliation,
                configuration=None,
            )

        elif reconciliation.decision != AdminConfigurationReconciliationDecision.IMPORT:
            raise RuntimeError(
                "Explicit ADMIN category selection produced unsupported decision "
                f"{reconciliation.decision.value}."
            )

        refreshed_category = self._discover_selected_category(
            guild,
            category_id=category_id,
        )

        if not refreshed_category.is_structurally_ready:
            raise RuntimeError(
                "The selected ADMIN category is still not usable after safe "
                "preparation."
            )

        return refreshed_category

    async def save_explicit_routing(
        self,
        guild: discord.Guild,
        *,
        category_id: int,
        command_channel_id: int,
        activity_forum_id: int,
        error_forum_id: int,
    ) -> GuildAdminConfiguration:
        """Validate and persist one human-selected ADMIN routing configuration."""

        category = await self.prepare_category(
            guild,
            category_id,
        )

        self._require_channel(
            category.usable_text_channels,
            channel_id=command_channel_id,
            label="administrative command channel",
        )

        self._require_channel(
            category.usable_forum_channels,
            channel_id=activity_forum_id,
            label="activity report forum",
        )

        self._require_channel(
            category.usable_forum_channels,
            channel_id=error_forum_id,
            label="error report forum",
        )

        if activity_forum_id == error_forum_id:
            raise ValueError("Activity and error forums must be different.")

        configuration = GuildAdminConfiguration(
            guild_id=guild.id,
            category_id=category.category_id,
            command_channel_id=command_channel_id,
            activity_forum_id=activity_forum_id,
            error_forum_id=error_forum_id,
        )

        await self.repository.save(
            configuration,
        )

        return configuration

    def _discover_selected_category(
        self,
        guild: discord.Guild,
        *,
        category_id: int,
    ) -> AdminCategoryCandidate:
        """Rediscover one explicitly selected category by Discord identity."""

        discovery = self.discovery_service.discover(
            guild,
            configured_category_id=category_id,
        )

        category = next(
            (
                candidate
                for candidate in discovery.categories
                if candidate.category_id == category_id
            ),
            None,
        )

        if category is None:
            raise RuntimeError(
                f"Selected ADMIN category {category_id} no longer exists."
            )

        return category

    @staticmethod
    def _require_channel(
        channels: tuple[AdminChannelCandidate, ...],
        *,
        channel_id: int,
        label: str,
    ) -> AdminChannelCandidate:
        """Resolve one selected channel from the currently usable candidates."""

        if channel_id <= 0:
            raise ValueError(f"Selected {label} ID must be greater than zero.")

        channel = next(
            (
                candidate
                for candidate in channels
                if candidate.channel_id == channel_id
            ),
            None,
        )

        if channel is None:
            raise ValueError(
                f"Selected {label} {channel_id} is not usable in this ADMIN category."
            )

        return channel
