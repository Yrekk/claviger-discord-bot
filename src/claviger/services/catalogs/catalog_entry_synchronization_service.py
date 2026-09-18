from collections import Counter

import discord

from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
    CatalogTargetVariant,
)
from claviger.models.catalogs.role_channel_discovery_model import (
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)
from claviger.services.catalogs.catalog_variant_classifier import (
    CatalogVariantClassifier,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)

_VARIANT_COLLISION_SUFFIX = "--ai-variants"


class CatalogEntrySynchronizationError(RuntimeError):
    """Raised when live Discord catalog discovery is ambiguous."""


class CatalogEntrySynchronizationService:
    """Discover one configured catalog and refresh its V11 generic storage."""

    def __init__(
        self,
        *,
        repository: CatalogEntryRepository,
        discovery_service: RoleChannelDiscoveryService,
        variant_classifier: CatalogVariantClassifier,
    ) -> None:
        self.repository = repository
        self.discovery_service = discovery_service
        self.variant_classifier = variant_classifier

    async def synchronize(
        self,
        *,
        guild: discord.Guild,
        catalog: CatalogDefinition,
    ) -> tuple[CatalogEntry, ...]:
        """Synchronize valid role/channel targets, then reload canonical rows."""

        if catalog.guild_id != guild.id:
            raise CatalogEntrySynchronizationError(
                "Catalog definition belongs to another Discord guild."
            )

        snapshot = self.discovery_service.build_snapshot(
            guild,
        )
        discovered = self._build_entries(
            catalog=catalog,
            snapshot=snapshot,
        )

        await self.repository.sync_discovered_catalog(
            guild_id=guild.id,
            catalog_key=catalog.catalog_key,
            entries=discovered,
        )

        return await self.repository.list_for_catalog(
            guild_id=guild.id,
            catalog_key=catalog.catalog_key,
        )

    def _build_entries(
        self,
        *,
        catalog: CatalogDefinition,
        snapshot: GuildRoleChannelSnapshot,
    ) -> tuple[CatalogEntry, ...]:
        """Convert live role suffixes into logical base/AI catalog entries."""

        raw_roles: list[tuple[str, DiscordRoleSnapshot]] = []

        for role in snapshot.roles:
            if not role.role_name.startswith(
                catalog.role_prefix,
            ):
                continue

            raw_key = role.role_name[
                len(catalog.role_prefix) :
            ].strip()

            if raw_key:
                raw_roles.append(
                    (
                        raw_key,
                        role,
                    )
                )

        counts = Counter(
            raw_key
            for raw_key, _ in raw_roles
        )
        duplicates = tuple(
            sorted(
                key
                for key, count in counts.items()
                if count > 1
            )
        )

        if duplicates:
            raise CatalogEntrySynchronizationError(
                "Several Discord roles resolve to the same catalog key: "
                + ", ".join(duplicates)
            )

        roles_by_key = {
            raw_key: role
            for raw_key, role in raw_roles
        }
        classification = self.variant_classifier.classify(
            roles_by_key,
        )

        if classification.invalid_keys or classification.duplicate_keys:
            raise CatalogEntrySynchronizationError(
                "Catalog role names contain invalid or duplicate variant keys."
            )

        groups: list[
            tuple[
                str,
                tuple[
                    tuple[str, CatalogTargetVariant],
                    ...,
                ],
            ]
        ] = []

        for key in classification.solo_keys:
            groups.append(
                (
                    key,
                    (
                        (
                            key,
                            "base",
                        ),
                    ),
                )
            )

        singleton_keys = set(
            classification.solo_keys,
        )
        variant_theme_keys = {
            pair.theme_key
            for pair in classification.pairs
        }
        variant_theme_keys.update(
            key.removeprefix(
                self.variant_classifier.AI_PREFIX,
            )
            for key in classification.ai_only_keys
        )
        variant_theme_keys.update(
            key.removeprefix(
                self.variant_classifier.NO_AI_PREFIX,
            )
            for key in classification.no_ai_only_keys
        )
        used_keys = set(
            singleton_keys,
        )

        for pair in classification.pairs:
            entry_key = self._allocate_variant_entry_key(
                pair.theme_key,
                singleton_keys=singleton_keys,
                variant_theme_keys=variant_theme_keys,
                used_keys=used_keys,
            )
            used_keys.add(
                entry_key,
            )
            groups.append(
                (
                    entry_key,
                    (
                        (
                            pair.no_ai_key,
                            "no_ai",
                        ),
                        (
                            pair.ai_key,
                            "ai",
                        ),
                    ),
                )
            )

        for raw_key in classification.no_ai_only_keys:
            groups.append(
                (
                    raw_key.removeprefix(
                        self.variant_classifier.NO_AI_PREFIX,
                    ),
                    (
                        (
                            raw_key,
                            "no_ai",
                        ),
                    ),
                )
            )

        for raw_key in classification.ai_only_keys:
            groups.append(
                (
                    raw_key.removeprefix(
                        self.variant_classifier.AI_PREFIX,
                    ),
                    (
                        (
                            raw_key,
                            "ai",
                        ),
                    ),
                )
            )

        entry_keys = [
            entry_key
            for entry_key, _ in groups
        ]

        if len(entry_keys) != len(set(entry_keys)):
            raise CatalogEntrySynchronizationError(
                "Catalog singleton and AI variants collide on one logical key."
            )

        channels_by_id = {
            channel.channel_id: channel
            for channel in snapshot.channels
        }
        entries: list[CatalogEntry] = []

        for entry_key, target_specs in groups:
            targets: list[CatalogEntryTarget] = []

            for raw_key, variant in target_specs:
                role = roles_by_key[raw_key]

                if len(role.explicit_channel_ids) != 1:
                    continue

                channel = channels_by_id.get(
                    role.explicit_channel_ids[0],
                )

                if channel is None:
                    continue

                targets.append(
                    CatalogEntryTarget(
                        guild_id=catalog.guild_id,
                        catalog_key=catalog.catalog_key,
                        entry_key=entry_key,
                        role_id=role.role_id,
                        role_name=role.role_name,
                        channel_id=channel.channel_id,
                        channel_name=channel.channel_name,
                        variant=variant,
                        enabled=True,
                        discord_present=True,
                        role_manageable=role.role_manageable,
                        channel_present=True,
                        mapping_valid=True,
                        matches_policy=True,
                    )
                )

            if not targets:
                continue

            entries.append(
                CatalogEntry(
                    guild_id=catalog.guild_id,
                    catalog_key=catalog.catalog_key,
                    entry_key=entry_key,
                    label=None,
                    description=None,
                    emoji=None,
                    sort_order=0,
                    enabled=True,
                    targets=tuple(
                        targets,
                    ),
                )
            )

        return tuple(
            sorted(
                entries,
                key=lambda entry: entry.entry_key,
            )
        )

    @staticmethod
    def _allocate_variant_entry_key(
        theme_key: str,
        *,
        singleton_keys: set[str],
        variant_theme_keys: set[str],
        used_keys: set[str],
    ) -> str:
        """Match V11 migration collision semantics for stable logical identities."""

        if theme_key not in used_keys:
            return theme_key

        stem = f"{theme_key}{_VARIANT_COLLISION_SUFFIX}"
        candidate = stem
        suffix = 2
        reserved_keys = singleton_keys | variant_theme_keys

        while candidate in reserved_keys or candidate in used_keys:
            candidate = f"{stem}-{suffix}"
            suffix += 1

        return candidate
