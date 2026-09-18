from pathlib import Path
from unittest.mock import MagicMock

import discord
import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.catalogs.catalog_definition_model import CatalogDefinition
from claviger.models.catalogs.role_channel_discovery_model import (
    DiscordChannelSnapshot,
    DiscordRoleSnapshot,
    GuildRoleChannelSnapshot,
)
from claviger.repositories.catalogs.catalog_entry_repository import CatalogEntryRepository
from claviger.services.catalogs.catalog_entry_synchronization_service import (
    CatalogEntrySynchronizationService,
)
from claviger.services.catalogs.catalog_variant_classifier import (
    CatalogVariantClassifier,
)
from claviger.services.catalogs.role_channel_discovery_service import (
    RoleChannelDiscoveryService,
)

pytestmark = pytest.mark.asyncio


async def test_sync_discovers_base_and_ai_variant_entries(
    tmp_path: Path,
) -> None:
    """Persist live prefix matches using the same logical variant semantics as V11."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    await DatabaseSchema(
        database,
    ).initialize()

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_catalogs (
                guild_id, catalog_key, role_prefix, display_name, entry_name
            )
            VALUES (123, 'movie', 'movie-', 'Cinéma', 'Option')
            """
        )
        await connection.commit()

    discovery = MagicMock(spec=RoleChannelDiscoveryService)
    discovery.build_snapshot.return_value = GuildRoleChannelSnapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=501,
                role_name="movie-classique",
                role_manageable=True,
                explicit_channel_ids=(1501,),
            ),
            DiscordRoleSnapshot(
                role_id=502,
                role_name="movie-no-ia-studio",
                role_manageable=True,
                explicit_channel_ids=(1502,),
            ),
            DiscordRoleSnapshot(
                role_id=503,
                role_name="movie-ia-studio",
                role_manageable=True,
                explicit_channel_ids=(1503,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=1501,
                channel_name="classique",
            ),
            DiscordChannelSnapshot(
                channel_id=1502,
                channel_name="studio-standard",
            ),
            DiscordChannelSnapshot(
                channel_id=1503,
                channel_name="studio-ia",
            ),
        ),
    )

    repository = CatalogEntryRepository(
        database,
    )
    service = CatalogEntrySynchronizationService(
        repository=repository,
        discovery_service=discovery,
        variant_classifier=CatalogVariantClassifier(),
    )
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123

    result = await service.synchronize(
        guild=guild,
        catalog=CatalogDefinition(
            guild_id=123,
            catalog_key="movie",
            role_prefix="movie-",
            display_name="Cinéma",
            entry_name="Option",
            description=None,
            sort_order=0,
            enabled=True,
        ),
    )

    assert tuple(entry.entry_key for entry in result) == (
        "classique",
        "studio",
    )
    studio = result[1]
    assert tuple(target.variant for target in studio.targets) == (
        "no_ai",
        "ai",
    )
    assert tuple(target.role_id for target in studio.targets) == (
        502,
        503,
    )


async def test_sync_preserves_human_metadata_on_rediscovery(
    tmp_path: Path,
) -> None:
    """Refresh Discord-owned fields without erasing labels or descriptions."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )
    await DatabaseSchema(
        database,
    ).initialize()

    async with database.connect() as connection:
        await connection.execute(
            """
            INSERT INTO guild_catalogs (
                guild_id, catalog_key, role_prefix, display_name, entry_name
            )
            VALUES (123, 'movie', 'movie-', 'Cinéma', 'Option')
            """
        )
        await connection.execute(
            """
            INSERT INTO guild_catalog_entries (
                guild_id, catalog_key, entry_key, label, description
            )
            VALUES (123, 'movie', 'classique', 'Classiques', 'Films classiques')
            """
        )
        await connection.commit()

    discovery = MagicMock(spec=RoleChannelDiscoveryService)
    discovery.build_snapshot.return_value = GuildRoleChannelSnapshot(
        roles=(
            DiscordRoleSnapshot(
                role_id=501,
                role_name="movie-classique",
                role_manageable=True,
                explicit_channel_ids=(1501,),
            ),
        ),
        channels=(
            DiscordChannelSnapshot(
                channel_id=1501,
                channel_name="classique",
            ),
        ),
    )

    repository = CatalogEntryRepository(
        database,
    )
    service = CatalogEntrySynchronizationService(
        repository=repository,
        discovery_service=discovery,
        variant_classifier=CatalogVariantClassifier(),
    )
    guild = MagicMock(spec=discord.Guild)
    guild.id = 123

    result = await service.synchronize(
        guild=guild,
        catalog=CatalogDefinition(
            guild_id=123,
            catalog_key="movie",
            role_prefix="movie-",
            display_name="Cinéma",
            entry_name="Option",
            description=None,
            sort_order=0,
            enabled=True,
        ),
    )

    assert result[0].label == "Classiques"
    assert result[0].description == "Films classiques"
