from unittest.mock import AsyncMock, Mock

import pytest

from claviger.database.status import DatabaseState
from claviger.services.role_discovery import RoleDiscoveryService

from .helpers import create_test_group


def _get_database_command_names(
    *,
    database_state: DatabaseState,
    database_ownership_bound: bool,
) -> set[str]:
    """Return exposed database commands for one runtime state."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    role_discovery_service.get_hierarchy = AsyncMock()

    (
        group,
        _,
        _,
        _,
        _,
    ) = create_test_group(
        role_discovery_service,
        database_state=database_state,
        database_ownership_bound=database_ownership_bound,
    )

    database_group = group.get_command(
        "database",
    )

    assert database_group is not None

    return {command.name for command in database_group.commands}


@pytest.mark.parametrize(
    "database_state",
    [
        DatabaseState.MISSING,
        DatabaseState.UNINITIALIZED,
    ],
)
def test_database_initialize_is_exposed_only_for_initializable_states(
    database_state: DatabaseState,
) -> None:
    """Expose initialization only before a schema exists."""

    assert _get_database_command_names(
        database_state=database_state,
        database_ownership_bound=False,
    ) == {
        "status",
        "initialize",
    }


def test_database_migrate_is_exposed_only_when_required() -> None:
    """Expose migration for an outdated initialized database."""

    assert _get_database_command_names(
        database_state=DatabaseState.MIGRATION_REQUIRED,
        database_ownership_bound=False,
    ) == {
        "status",
        "migrate",
    }


def test_database_bind_is_exposed_for_ready_unbound_database() -> None:
    """Expose binding only when the schema is ready but ownership is absent."""

    assert _get_database_command_names(
        database_state=DatabaseState.READY,
        database_ownership_bound=False,
    ) == {
        "status",
        "bind",
    }


def test_ready_owned_database_exposes_status_only() -> None:
    """Hide lifecycle actions once the database is fully operational."""

    assert _get_database_command_names(
        database_state=DatabaseState.READY,
        database_ownership_bound=True,
    ) == {
        "status",
    }


@pytest.mark.parametrize(
    "database_state",
    [
        DatabaseState.TOO_NEW,
        DatabaseState.UNAVAILABLE,
    ],
)
def test_unsafe_database_states_expose_status_only(
    database_state: DatabaseState,
) -> None:
    """Never propose a mutating lifecycle action for unsafe states."""

    assert _get_database_command_names(
        database_state=database_state,
        database_ownership_bound=False,
    ) == {
        "status",
    }
