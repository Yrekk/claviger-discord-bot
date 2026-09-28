from dataclasses import dataclass
from enum import StrEnum

import aiosqlite

from claviger.database.connection import (
    DatabaseConnection,
    DatabaseUnavailableError,
)
from claviger.database.schema import (
    APPLICATION_TABLE_NAMES,
    CURRENT_SCHEMA_VERSION,
    DatabaseSchema,
)
from claviger.models.inspection import InspectionFinding


class DatabaseState(StrEnum):
    """Shared Nexus-compatible lifecycle classifications."""

    MISSING = "missing"
    UNINITIALIZED = "uninitialized"
    READY = "ready"
    MIGRATION_REQUIRED = "migration_required"
    TOO_NEW = "too_new"
    UNAVAILABLE = "unavailable"
    INVALID = "invalid"


class DatabaseFindingCode(StrEnum):
    """Canonical Nexus-compatible finding codes used by Claviger."""

    RESOURCE_MISSING = "database.resource.missing"
    RESOURCE_PATH_NOT_FILE = "database.resource.path_not_file"
    RESOURCE_UNAVAILABLE = "database.resource.unavailable"
    INTEGRITY_FAILED = "database.integrity.failed"
    SCHEMA_UNINITIALIZED = "database.schema.uninitialized"
    APPLICATION_HISTORY_ABSENT = "database.schema.application_history_absent"
    USER_OBJECTS_ABSENT = "database.schema.user_objects_absent"
    NON_APPLICATION_OBJECTS_PRESENT = (
        "database.schema.non_application_objects_present"
    )
    SCHEMA_CURRENT = "database.schema.current"
    SCHEMA_OUTDATED = "database.schema.outdated"
    SCHEMA_NEWER_THAN_RUNTIME = "database.schema.newer_than_runtime"
    SCHEMA_HISTORY_INCONSISTENT = "database.schema.history_inconsistent"
    SCHEMA_READ_FAILED = "database.schema.read_failed"


@dataclass(frozen=True, slots=True)
class DatabaseInspectionFacts:
    """Technical facts observed without mutating the database."""

    file_exists: bool
    path_occupied_by_non_file: bool
    accessible: bool
    integrity_valid: bool | None
    current_version: int | None
    target_version: int
    user_object_count: int | None
    application_object_count: int | None


@dataclass(frozen=True, slots=True, init=False)
class DatabaseStatus:
    """Structured database inspection result.

    State is resolved only when exactly one candidate remains. A suggestion is
    never silently promoted into administrative authority.
    """

    facts: DatabaseInspectionFacts
    candidate_states: tuple[DatabaseState, ...]
    suggested_state: DatabaseState
    findings: tuple[InspectionFinding, ...]

    def __init__(
        self,
        *,
        facts: DatabaseInspectionFacts | None = None,
        candidate_states: tuple[DatabaseState, ...] | None = None,
        suggested_state: DatabaseState | None = None,
        findings: tuple[InspectionFinding, ...] | None = None,
        state: DatabaseState | None = None,
        current_version: int | None = None,
        target_version: int = CURRENT_SCHEMA_VERSION,
    ) -> None:
        """Create a complete inspection or a deterministic resolved shorthand."""

        if facts is None:
            if state is None:
                raise ValueError(
                    "facts are required when no deterministic state is supplied."
                )

            facts = DatabaseInspectionFacts(
                file_exists=state is not DatabaseState.MISSING,
                path_occupied_by_non_file=False,
                accessible=state not in (
                    DatabaseState.MISSING,
                    DatabaseState.UNAVAILABLE,
                ),
                integrity_valid=(
                    None
                    if state
                    in (
                        DatabaseState.MISSING,
                        DatabaseState.UNAVAILABLE,
                    )
                    else state is not DatabaseState.INVALID
                ),
                current_version=current_version,
                target_version=target_version,
                user_object_count=None,
                application_object_count=None,
            )

        if candidate_states is None:
            if state is None:
                raise ValueError("candidate_states must not be empty.")

            candidate_states = (state,)

        candidate_states = tuple(dict.fromkeys(candidate_states))

        if not candidate_states:
            raise ValueError("candidate_states must not be empty.")

        if suggested_state is None:
            suggested_state = state or candidate_states[0]

        if suggested_state not in candidate_states:
            raise ValueError("suggested_state must be one of candidate_states.")

        if state is not None and candidate_states != (state,):
            raise ValueError(
                "state shorthand can only represent one resolved candidate."
            )

        if findings is None:
            findings = (_default_finding(suggested_state, facts),)

        if not findings:
            raise ValueError("findings must not be empty.")

        object.__setattr__(self, "facts", facts)
        object.__setattr__(self, "candidate_states", candidate_states)
        object.__setattr__(self, "suggested_state", suggested_state)
        object.__setattr__(self, "findings", tuple(findings))

    @property
    def state(self) -> DatabaseState | None:
        """Return the resolved classification or None while Admin choice is needed."""

        if len(self.candidate_states) != 1:
            return None

        return self.candidate_states[0]

    @property
    def requires_administrator_classification(self) -> bool:
        """Return whether several fact-compatible classifications remain."""

        return len(self.candidate_states) > 1

    @property
    def current_version(self) -> int | None:
        return self.facts.current_version

    @property
    def target_version(self) -> int:
        return self.facts.target_version


def _default_finding(
    state: DatabaseState,
    facts: DatabaseInspectionFacts,
) -> InspectionFinding:
    code_by_state = {
        DatabaseState.MISSING: DatabaseFindingCode.RESOURCE_MISSING,
        DatabaseState.UNINITIALIZED: DatabaseFindingCode.SCHEMA_UNINITIALIZED,
        DatabaseState.READY: DatabaseFindingCode.SCHEMA_CURRENT,
        DatabaseState.MIGRATION_REQUIRED: DatabaseFindingCode.SCHEMA_OUTDATED,
        DatabaseState.TOO_NEW: DatabaseFindingCode.SCHEMA_NEWER_THAN_RUNTIME,
        DatabaseState.UNAVAILABLE: DatabaseFindingCode.RESOURCE_UNAVAILABLE,
        DatabaseState.INVALID: DatabaseFindingCode.SCHEMA_HISTORY_INCONSISTENT,
    }

    details: dict[str, int] = {
        "target_version": facts.target_version,
    }

    if facts.current_version is not None:
        details["current_version"] = facts.current_version

    return InspectionFinding(
        code=code_by_state[state].value,
        details=details,
    )


class DatabaseStatusService:
    """Inspect Claviger's database without modifying it."""

    _TRANSIENT_SQLITE_CODES = frozenset(
        {
            5,
            6,
            10,
            14,
        }
    )

    def __init__(
        self,
        database: DatabaseConnection,
        schema: DatabaseSchema,
    ) -> None:
        self.database = database
        self.schema = schema

    async def check(self) -> DatabaseStatus:
        """Return facts, findings and compatible states without mutation."""

        path = self.database.database_path

        if not path.exists():
            return self._resolved(
                state=DatabaseState.MISSING,
                facts=DatabaseInspectionFacts(
                    file_exists=False,
                    path_occupied_by_non_file=False,
                    accessible=False,
                    integrity_valid=None,
                    current_version=None,
                    target_version=CURRENT_SCHEMA_VERSION,
                    user_object_count=None,
                    application_object_count=None,
                ),
                findings=(
                    InspectionFinding(
                        DatabaseFindingCode.RESOURCE_MISSING.value,
                    ),
                ),
            )

        if not path.is_file():
            return self._resolved(
                state=DatabaseState.UNAVAILABLE,
                facts=DatabaseInspectionFacts(
                    file_exists=False,
                    path_occupied_by_non_file=True,
                    accessible=False,
                    integrity_valid=None,
                    current_version=None,
                    target_version=CURRENT_SCHEMA_VERSION,
                    user_object_count=None,
                    application_object_count=None,
                ),
                findings=(
                    InspectionFinding(
                        DatabaseFindingCode.RESOURCE_PATH_NOT_FILE.value,
                    ),
                ),
            )

        integrity_valid: bool | None = None

        try:
            async with self.database.connect() as connection:
                integrity_valid = await self._check_integrity(connection)

                if not integrity_valid:
                    return self._invalid(
                        integrity_valid=False,
                        finding=InspectionFinding(
                            DatabaseFindingCode.INTEGRITY_FAILED.value,
                        ),
                    )

                current_version = await self._get_version(connection)
                table_names = await self._get_table_names(connection)

        except DatabaseUnavailableError:
            return self._unavailable()

        except aiosqlite.Error as error:
            error_code = getattr(
                error,
                "sqlite_errorcode",
                None,
            )

            if error_code in self._TRANSIENT_SQLITE_CODES:
                return self._unavailable(
                    provider_error_code=error_code,
                )

            return self._invalid(
                integrity_valid=integrity_valid is True,
                finding=InspectionFinding(
                    (
                        DatabaseFindingCode.SCHEMA_READ_FAILED.value
                        if integrity_valid
                        else DatabaseFindingCode.INTEGRITY_FAILED.value
                    ),
                    details=(
                        {}
                        if error_code is None
                        else {"provider_error_code": error_code}
                    ),
                ),
            )

        application_tables = set(table_names) & APPLICATION_TABLE_NAMES
        non_application_tables = set(table_names) - APPLICATION_TABLE_NAMES

        facts = DatabaseInspectionFacts(
            file_exists=True,
            path_occupied_by_non_file=False,
            accessible=True,
            integrity_valid=True,
            current_version=current_version,
            target_version=CURRENT_SCHEMA_VERSION,
            user_object_count=len(table_names),
            application_object_count=len(application_tables),
        )

        if current_version == 0:
            if application_tables:
                return DatabaseStatus(
                    facts=facts,
                    candidate_states=(DatabaseState.INVALID,),
                    suggested_state=DatabaseState.INVALID,
                    findings=(
                        InspectionFinding(
                            DatabaseFindingCode.SCHEMA_UNINITIALIZED.value,
                        ),
                        InspectionFinding(
                            DatabaseFindingCode.SCHEMA_HISTORY_INCONSISTENT.value,
                            details={
                                "object_count": len(application_tables),
                            },
                        ),
                    ),
                )

            findings = [
                InspectionFinding(
                    DatabaseFindingCode.SCHEMA_UNINITIALIZED.value,
                ),
                InspectionFinding(
                    DatabaseFindingCode.APPLICATION_HISTORY_ABSENT.value,
                ),
            ]

            if non_application_tables:
                findings.append(
                    InspectionFinding(
                        DatabaseFindingCode.NON_APPLICATION_OBJECTS_PRESENT.value,
                        details={
                            "object_count": len(non_application_tables),
                        },
                    )
                )
                suggested_state = DatabaseState.INVALID

            else:
                findings.append(
                    InspectionFinding(
                        DatabaseFindingCode.USER_OBJECTS_ABSENT.value,
                    )
                )
                suggested_state = DatabaseState.UNINITIALIZED

            return DatabaseStatus(
                facts=facts,
                candidate_states=(
                    DatabaseState.UNINITIALIZED,
                    DatabaseState.INVALID,
                ),
                suggested_state=suggested_state,
                findings=tuple(findings),
            )

        if current_version < CURRENT_SCHEMA_VERSION:
            return self._resolved(
                state=DatabaseState.MIGRATION_REQUIRED,
                facts=facts,
                findings=(
                    InspectionFinding(
                        DatabaseFindingCode.SCHEMA_OUTDATED.value,
                        details={
                            "current_version": current_version,
                            "target_version": CURRENT_SCHEMA_VERSION,
                            "pending_count": (
                                CURRENT_SCHEMA_VERSION - current_version
                            ),
                        },
                    ),
                ),
            )

        if current_version > CURRENT_SCHEMA_VERSION:
            return self._resolved(
                state=DatabaseState.TOO_NEW,
                facts=facts,
                findings=(
                    InspectionFinding(
                        DatabaseFindingCode.SCHEMA_NEWER_THAN_RUNTIME.value,
                        details={
                            "current_version": current_version,
                            "target_version": CURRENT_SCHEMA_VERSION,
                        },
                    ),
                ),
            )

        return self._resolved(
            state=DatabaseState.READY,
            facts=facts,
            findings=(
                InspectionFinding(
                    DatabaseFindingCode.SCHEMA_CURRENT.value,
                    details={
                        "current_version": current_version,
                        "target_version": CURRENT_SCHEMA_VERSION,
                    },
                ),
            ),
        )

    @staticmethod
    async def _check_integrity(
        connection: aiosqlite.Connection,
    ) -> bool:
        cursor = await connection.execute("PRAGMA quick_check")
        rows = await cursor.fetchall()

        return bool(rows) and all(
            str(row[0]).lower() == "ok"
            for row in rows
        )

    @staticmethod
    async def _get_version(
        connection: aiosqlite.Connection,
    ) -> int:
        cursor = await connection.execute("PRAGMA user_version")
        row = await cursor.fetchone()

        return 0 if row is None else int(row[0])

    @staticmethod
    async def _get_table_names(
        connection: aiosqlite.Connection,
    ) -> tuple[str, ...]:
        cursor = await connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        rows = await cursor.fetchall()

        return tuple(
            str(row[0])
            for row in rows
        )

    @staticmethod
    def _resolved(
        *,
        state: DatabaseState,
        facts: DatabaseInspectionFacts,
        findings: tuple[InspectionFinding, ...],
    ) -> DatabaseStatus:
        return DatabaseStatus(
            facts=facts,
            candidate_states=(state,),
            suggested_state=state,
            findings=findings,
        )

    @staticmethod
    def _unavailable(
        *,
        provider_error_code: int | None = None,
    ) -> DatabaseStatus:
        details = (
            {}
            if provider_error_code is None
            else {"provider_error_code": provider_error_code}
        )

        return DatabaseStatus(
            facts=DatabaseInspectionFacts(
                file_exists=True,
                path_occupied_by_non_file=False,
                accessible=False,
                integrity_valid=None,
                current_version=None,
                target_version=CURRENT_SCHEMA_VERSION,
                user_object_count=None,
                application_object_count=None,
            ),
            candidate_states=(DatabaseState.UNAVAILABLE,),
            suggested_state=DatabaseState.UNAVAILABLE,
            findings=(
                InspectionFinding(
                    DatabaseFindingCode.RESOURCE_UNAVAILABLE.value,
                    details=details,
                ),
            ),
        )

    @staticmethod
    def _invalid(
        *,
        integrity_valid: bool,
        finding: InspectionFinding,
    ) -> DatabaseStatus:
        return DatabaseStatus(
            facts=DatabaseInspectionFacts(
                file_exists=True,
                path_occupied_by_non_file=False,
                accessible=True,
                integrity_valid=integrity_valid,
                current_version=None,
                target_version=CURRENT_SCHEMA_VERSION,
                user_object_count=None,
                application_object_count=None,
            ),
            candidate_states=(DatabaseState.INVALID,),
            suggested_state=DatabaseState.INVALID,
            findings=(finding,),
        )
