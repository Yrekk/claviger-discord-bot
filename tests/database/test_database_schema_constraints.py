from pathlib import Path

import aiosqlite
import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema


async def _create_database(
    tmp_path: Path,
) -> DatabaseConnection:
    """Create one database using the current schema."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    return database


async def _insert_workflow(
    connection: aiosqlite.Connection,
    *,
    guild_id: int = 123,
    workflow_key: str = "member",
    command_name: str = "membre",
) -> None:
    """Insert one valid workflow definition."""

    await connection.execute(
        """
        INSERT INTO guild_workflows (
            guild_id,
            workflow_key,
            command_name,
            command_description,
            title,
            policy_key
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            workflow_key,
            command_name,
            "Configure member preferences.",
            "Member preferences",
            "public",
        ),
    )


async def _insert_catalog(
    connection: aiosqlite.Connection,
    *,
    guild_id: int = 123,
    catalog_key: str = "interests",
    role_prefix: str = "interest-",
) -> None:
    """Insert one valid catalog definition."""

    await connection.execute(
        """
        INSERT INTO guild_catalogs (
            guild_id,
            catalog_key,
            role_prefix,
            display_name,
            entry_name
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            catalog_key,
            role_prefix,
            "Interests",
            "Interest",
        ),
    )


@pytest.mark.asyncio
async def test_member_interest_requires_channel_mapping(
    tmp_path: Path,
) -> None:
    """Reject member interests without a Discord channel mapping."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_member_interests (
                    guild_id,
                    role_id,
                    role_name,
                    interest_key
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    123,
                    456,
                    "interest-test",
                    "test",
                ),
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_adult_access_requires_channel_mapping(
    tmp_path: Path,
) -> None:
    """Reject adult accesses without a Discord channel mapping."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_adult_accesses (
                    guild_id,
                    role_id,
                    role_name,
                    access_key
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    123,
                    456,
                    "access-ia-test",
                    "ia-test",
                ),
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_workflow_command_name_is_unique_per_guild(
    tmp_path: Path,
) -> None:
    """Reject ambiguous command routing inside one guild."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_workflow(
            connection,
        )

        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await _insert_workflow(
                connection,
                workflow_key="other-member",
                command_name="membre",
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_same_command_name_is_allowed_in_different_guilds(
    tmp_path: Path,
) -> None:
    """Allow each guild to define its own command routing."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_workflow(
            connection,
            guild_id=123,
        )

        await _insert_workflow(
            connection,
            guild_id=456,
        )

        await connection.commit()


@pytest.mark.asyncio
async def test_catalog_prefix_is_unique_per_guild(
    tmp_path: Path,
) -> None:
    """Reject two catalog definitions owning the exact same role prefix."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_catalog(
            connection,
        )

        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await _insert_catalog(
                connection,
                catalog_key="other-interests",
                role_prefix="interest-",
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_overlapping_catalog_prefixes_are_allowed(
    tmp_path: Path,
) -> None:
    """Allow specific catalog prefixes to overlap broader prefixes."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_catalog(
            connection,
            catalog_key="access",
            role_prefix="access-",
        )

        await _insert_catalog(
            connection,
            catalog_key="premium-access",
            role_prefix="access-premium-",
        )

        await connection.commit()


@pytest.mark.asyncio
async def test_workflow_channel_uses_positive_discord_id(
    tmp_path: Path,
) -> None:
    """Persist workflow channel routing using a positive Discord ID."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_workflow(
            connection,
        )

        await connection.execute(
            """
            INSERT INTO guild_workflow_channels (
                guild_id,
                workflow_key,
                channel_id
            )
            VALUES (?, ?, ?)
            """,
            (
                123,
                "member",
                987654321,
            ),
        )

        await connection.commit()

        cursor = await connection.execute(
            """
            SELECT channel_id
            FROM guild_workflow_channels
            WHERE guild_id = ?
              AND workflow_key = ?
            """,
            (
                123,
                "member",
            ),
        )

        row = await cursor.fetchone()

    assert row == (987654321,)


@pytest.mark.asyncio
async def test_workflow_channel_rejects_non_positive_discord_id(
    tmp_path: Path,
) -> None:
    """Reject invalid Discord channel identifiers."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_workflow(
            connection,
        )

        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_workflow_channels (
                    guild_id,
                    workflow_key,
                    channel_id
                )
                VALUES (?, ?, ?)
                """,
                (
                    123,
                    "member",
                    0,
                ),
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_workflow_catalog_requires_existing_workflow(
    tmp_path: Path,
) -> None:
    """Reject catalog bindings for an unknown workflow."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_catalog(
            connection,
        )

        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_workflow_catalogs (
                    guild_id,
                    workflow_key,
                    catalog_key
                )
                VALUES (?, ?, ?)
                """,
                (
                    123,
                    "missing-workflow",
                    "interests",
                ),
            )

        await connection.rollback()


@pytest.mark.asyncio
async def test_workflow_catalog_requires_existing_catalog(
    tmp_path: Path,
) -> None:
    """Reject workflow bindings for an unknown catalog."""

    database = await _create_database(
        tmp_path,
    )

    async with database.connect() as connection:
        await _insert_workflow(
            connection,
        )

        with pytest.raises(
            aiosqlite.IntegrityError,
        ):
            await connection.execute(
                """
                INSERT INTO guild_workflow_catalogs (
                    guild_id,
                    workflow_key,
                    catalog_key
                )
                VALUES (?, ?, ?)
                """,
                (
                    123,
                    "member",
                    "missing-catalog",
                ),
            )

        await connection.rollback()
