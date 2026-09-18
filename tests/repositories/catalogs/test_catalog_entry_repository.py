from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.models.catalogs.catalog_entry_model import (
    CatalogEntry,
    CatalogEntryTarget,
)
from claviger.repositories.catalogs.catalog_entry_repository import CatalogEntryRepository

pytestmark = pytest.mark.asyncio


async def test_repository_loads_logical_entry_with_variant_targets(
    tmp_path: Path,
) -> None:
    """Hydrate one logical entry with its no-AI and AI targets."""

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
            VALUES (123, 'access', 'access-', 'Accès', 'Accès')
            """
        )
        await connection.execute(
            """
            INSERT INTO guild_catalog_entries (
                guild_id, catalog_key, entry_key, label, description, sort_order
            )
            VALUES (123, 'access', 'casino', 'Casino', 'Accès casino', 10)
            """
        )
        for role_id, variant in (
            (501, "no_ai"),
            (502, "ai"),
        ):
            await connection.execute(
                """
                INSERT INTO guild_catalog_entry_targets (
                    guild_id, catalog_key, entry_key, role_id, role_name,
                    channel_id, channel_name, variant
                )
                VALUES (?, 'access', 'casino', ?, ?, ?, ?, ?)
                """,
                (
                    123,
                    role_id,
                    f"access-{variant}-casino",
                    role_id + 1000,
                    f"casino-{variant}",
                    variant,
                ),
            )
        await connection.commit()

    repository = CatalogEntryRepository(
        database,
    )

    result = await repository.list_for_catalog(
        guild_id=123,
        catalog_key="access",
    )

    assert result == (
        CatalogEntry(
            guild_id=123,
            catalog_key="access",
            entry_key="casino",
            label="Casino",
            description="Accès casino",
            emoji=None,
            sort_order=10,
            enabled=True,
            targets=(
                CatalogEntryTarget(
                    guild_id=123,
                    catalog_key="access",
                    entry_key="casino",
                    role_id=501,
                    role_name="access-no_ai-casino",
                    channel_id=1501,
                    channel_name="casino-no_ai",
                    variant="no_ai",
                    enabled=True,
                    discord_present=True,
                    role_manageable=True,
                    channel_present=True,
                    mapping_valid=True,
                    matches_policy=True,
                ),
                CatalogEntryTarget(
                    guild_id=123,
                    catalog_key="access",
                    entry_key="casino",
                    role_id=502,
                    role_name="access-ai-casino",
                    channel_id=1502,
                    channel_name="casino-ai",
                    variant="ai",
                    enabled=True,
                    discord_present=True,
                    role_manageable=True,
                    channel_present=True,
                    mapping_valid=True,
                    matches_policy=True,
                ),
            ),
        ),
    )
