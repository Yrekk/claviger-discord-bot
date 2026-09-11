from pathlib import Path

import pytest

from claviger.database.connection import DatabaseConnection
from claviger.database.schema import DatabaseSchema
from claviger.repositories.database_ownership_repository import (
    DatabaseOwnershipRepository,
)
from claviger.services.database_ownership_service import (
    DatabaseOwnershipMismatchError,
    DatabaseOwnershipService,
    DatabaseOwnershipUnboundError,
)

pytestmark = pytest.mark.asyncio


async def create_service(
    tmp_path: Path,
) -> DatabaseOwnershipService:
    """Create an initialized database with ownership support."""

    database = DatabaseConnection(
        tmp_path / "claviger.db",
    )

    schema = DatabaseSchema(
        database,
    )

    await schema.initialize()

    repository = DatabaseOwnershipRepository(
        database,
    )

    return DatabaseOwnershipService(
        repository,
    )


async def test_new_database_is_unbound(
    tmp_path: Path,
) -> None:
    """Keep application ownership empty until explicitly established."""

    service = await create_service(
        tmp_path,
    )

    assert await service.get_owner_application_id() is None


async def test_bind_assigns_application_owner(
    tmp_path: Path,
) -> None:
    """Bind an unowned database to one Discord application."""

    service = await create_service(
        tmp_path,
    )

    await service.bind(
        123456,
    )

    assert await service.get_owner_application_id() == 123456


async def test_bind_is_idempotent_for_same_application(
    tmp_path: Path,
) -> None:
    """Allow the owning application to confirm its existing binding."""

    service = await create_service(
        tmp_path,
    )

    await service.bind(
        123456,
    )

    await service.bind(
        123456,
    )

    assert await service.get_owner_application_id() == 123456


async def test_bind_rejects_different_application(
    tmp_path: Path,
) -> None:
    """Never allow another Discord application to claim an owned database."""

    service = await create_service(
        tmp_path,
    )

    await service.bind(
        123456,
    )

    with pytest.raises(
        DatabaseOwnershipMismatchError,
        match="belongs to another Discord application",
    ):
        await service.bind(
            999999,
        )

    assert await service.get_owner_application_id() == 123456


async def test_validate_accepts_database_owner(
    tmp_path: Path,
) -> None:
    """Accept the Discord application owning the database."""

    service = await create_service(
        tmp_path,
    )

    await service.bind(
        123456,
    )

    await service.validate(
        123456,
    )


async def test_validate_rejects_unbound_database(
    tmp_path: Path,
) -> None:
    """Fail closed while the database has no application owner."""

    service = await create_service(
        tmp_path,
    )

    with pytest.raises(
        DatabaseOwnershipUnboundError,
        match="not bound",
    ):
        await service.validate(
            123456,
        )


async def test_validate_rejects_different_application(
    tmp_path: Path,
) -> None:
    """Fail closed when another Discord application uses the database."""

    service = await create_service(
        tmp_path,
    )

    await service.bind(
        123456,
    )

    with pytest.raises(
        DatabaseOwnershipMismatchError,
        match="belongs to another Discord application",
    ):
        await service.validate(
            999999,
        )
