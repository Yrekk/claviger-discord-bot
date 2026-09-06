import aiosqlite
import discord

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseUnavailableError,
)
from claviger.models.catalog_sync_result_model import (
    CatalogSyncCatalogResult,
    CatalogSyncResult,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.catalog_registry_service import CatalogRegistry
from claviger.services.catalog_sync_planner_service import CatalogSyncPlanner
from claviger.services.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)


class CatalogSyncCoordinatorService:
    """Synchronize every registered role-to-channel catalog atomically."""

    def __init__(
        self,
        database: DatabaseConnection,
        registry: CatalogRegistry,
        discovery_service: RoleChannelDiscoveryService,
        planner: CatalogSyncPlanner,
    ) -> None:
        self.database = database
        self.registry = registry
        self.discovery_service = discovery_service
        self.planner = planner

    async def sync(
        self,
        guild: discord.Guild,
        policy: GuildPolicy,
    ) -> CatalogSyncResult:
        """Synchronize every catalog using one Discord snapshot."""

        snapshot = self.discovery_service.build_snapshot(
            guild,
        )

        definitions = self.registry.for_policy(
            policy,
        )

        catalog_results: list[CatalogSyncCatalogResult] = []

        for definition in definitions:
            current_entries = await definition.repository.list_for_guild(
                guild.id,
            )

            plan = self.planner.build_plan(
                current_entries,
                snapshot,
                prefix=definition.prefix,
            )

            catalog_results.append(
                CatalogSyncCatalogResult(
                    catalog_key=definition.catalog_key,
                    display_name=definition.display_name,
                    plan=plan,
                )
            )

        result = CatalogSyncResult(
            catalogs=tuple(catalog_results),
        )

        if result.change_count == 0:
            return result

        try:
            async with self.database.connect() as connection:
                await connection.execute("BEGIN IMMEDIATE")

                try:
                    for definition, catalog_result in zip(
                        definitions,
                        result.catalogs,
                        strict=True,
                    ):
                        await definition.repository.apply_sync_plan(
                            connection,
                            guild.id,
                            catalog_result.plan,
                        )

                    await connection.commit()

                except Exception:
                    await connection.rollback()
                    raise

        except aiosqlite.Error as error:
            raise DatabaseUnavailableError(
                (f"Unable to apply catalog synchronization for guild {guild.id}.")
            ) from error

        return result
