from claviger.models.catalog_next_selection_model import (
    CatalogNextSelection,
)
from claviger.policies.guild_policy import GuildPolicy
from claviger.services.catalog_registry_service import (
    CatalogRegistry,
)


class CatalogNotRegisteredError(LookupError):
    """Raised when a catalog key is not registered for the guild policy."""


class CatalogNextCoordinatorService:
    """Manage incomplete entries across all registered catalogs."""

    def __init__(
        self,
        registry: CatalogRegistry,
    ) -> None:
        self.registry = registry

    async def get_next(
        self,
        guild_id: int,
        policy: GuildPolicy,
    ) -> CatalogNextSelection | None:
        """Return the first incomplete entry following registry order."""

        definitions = self.registry.for_policy(
            policy,
        )

        for definition in definitions:
            entry = await definition.repository.get_next_incomplete(
                guild_id,
            )

            if entry is None:
                continue

            return CatalogNextSelection(
                catalog_key=definition.catalog_key,
                display_name=definition.display_name,
                entry_name=definition.entry_name,
                entry=entry,
            )

        return None

    async def update_metadata(
        self,
        guild_id: int,
        policy: GuildPolicy,
        catalog_key: str,
        role_id: int,
        *,
        label: str,
        description: str,
        emoji: str | None,
    ):
        """Update metadata through the repository owning the catalog."""

        definitions = self.registry.for_policy(
            policy,
        )

        for definition in definitions:
            if definition.catalog_key != catalog_key:
                continue

            return await definition.repository.update_metadata(
                guild_id,
                role_id,
                label=label,
                description=description,
                emoji=emoji,
            )

        raise CatalogNotRegisteredError(f"Catalog {catalog_key!r} is not registered.")
