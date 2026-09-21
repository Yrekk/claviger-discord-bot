from dataclasses import dataclass
from enum import StrEnum

from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)


class ApplicationRuntimeMode(StrEnum):
    """Describe the application-wide runtime degradation level."""

    NORMAL = "normal"
    RECOVERY = "recovery"
    MINIMAL = "minimal"
    HARD_STOP = "hard_stop"


class DatabaseOwnershipState(StrEnum):
    """Describe whether the current application may trust DB ownership."""

    NOT_EVALUATED = "not_evaluated"
    VALID = "valid"
    UNBOUND = "unbound"
    MISMATCH = "mismatch"


@dataclass(frozen=True, slots=True)
class ApplicationRuntimeState:
    """Describe application-wide DB trust and runtime capabilities."""

    mode: ApplicationRuntimeMode
    database_status: DatabaseStatus
    database_ownership_state: DatabaseOwnershipState

    @property
    def database_operational(self) -> bool:
        """Return whether normal persistent DB-backed operations are allowed."""

        return (
            self.mode is ApplicationRuntimeMode.NORMAL
            and self.database_status.state is DatabaseState.READY
            and self.database_ownership_state is DatabaseOwnershipState.VALID
        )

    @property
    def database_ownership_bound(self) -> bool:
        """Return whether the current application owns the database."""

        return self.database_ownership_state is DatabaseOwnershipState.VALID

    @property
    def database_bind_allowed(self) -> bool:
        """Return whether an explicit first ownership bind may be offered."""

        return (
            self.database_status.state is DatabaseState.READY
            and self.database_ownership_state is DatabaseOwnershipState.UNBOUND
        )
