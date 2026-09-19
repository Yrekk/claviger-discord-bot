from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.repositories.catalogs.catalog_entry_repository import (
    CatalogEntryRepository,
)

pytestmark = pytest.mark.asyncio


async def test_update_metadata_preserves_catalog_targets(
    tmp_path: Path,
) -> None:
    """Human metadata updates must never rewrite Discord target state."""

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
            VALUES (123, 'interest', 'interest-', 'Intérêts', 'Intérêt')
            """
        )
        await connection.execute(
            """
            INSERT INTO guild_catalog_entries (
                guild_id, catalog_key, entry_key
            )
            VALUES (123, 'interest', 'test')
            """
        )
        await connection.execute(
            """
            INSERT INTO guild_catalog_entry_targets (
                guild_id, catalog_key, entry_key, role_id, role_name,
                channel_id, channel_name, variant, role_manageable
            )
            VALUES (
                123, 'interest', 'test', 501, 'interest-test',
                1501, 'test-interest', 'base', 0
            )
            """
        )
        await connection.commit()

    repository = CatalogEntryRepository(
        database,
    )

    entry = await repository.update_metadata(
        guild_id=123,
        catalog_key="interest",
        entry_key="test",
        label="Test",
        description="Accès au salon de test.",
        emoji="🧪",
    )

    assert entry.label == "Test"
    assert entry.description == "Accès au salon de test."
    assert entry.emoji == "🧪"

    assert len(entry.targets) == 1
    target = entry.targets[0]
    assert target.role_id == 501
    assert target.role_name == "interest-test"
    assert target.channel_id == 1501
    assert target.channel_name == "test-interest"
    assert target.variant == "base"
    assert target.role_manageable is False
