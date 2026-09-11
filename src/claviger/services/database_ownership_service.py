from claviger.repositories.database_ownership_repository import (
    DatabaseOwnershipRepository,
)


class DatabaseOwnershipUnboundError(RuntimeError):
    """Raised when a database has no owning Discord application."""


class DatabaseOwnershipMismatchError(RuntimeError):
    """Raised when another Discord application owns the database."""


class DatabaseOwnershipService:
    """Validate and establish Discord application ownership of a database."""

    def __init__(
        self,
        repository: DatabaseOwnershipRepository,
    ) -> None:
        self.repository = repository

    async def get_owner_application_id(
        self,
    ) -> int | None:
        """Return the Discord application currently owning the database."""

        return await self.repository.get_application_id()

    async def bind(
        self,
        application_id: int,
    ) -> None:
        """Bind an unowned database or confirm an existing matching binding."""

        if application_id <= 0:
            raise ValueError("Discord application ID must be greater than zero.")

        current_owner = await self.repository.get_application_id()

        if current_owner is None:
            await self.repository.bind(
                application_id,
            )
            return

        if current_owner != application_id:
            raise DatabaseOwnershipMismatchError(
                "Database belongs to another Discord application. "
                f"Expected application_id={current_owner}, "
                f"received application_id={application_id}."
            )

    async def validate(
        self,
        application_id: int,
    ) -> None:
        """Fail closed unless the current Discord application owns the database."""

        if application_id <= 0:
            raise ValueError("Discord application ID must be greater than zero.")

        current_owner = await self.repository.get_application_id()

        if current_owner is None:
            raise DatabaseOwnershipUnboundError(
                "Database is not bound to a Discord application."
            )

        if current_owner != application_id:
            raise DatabaseOwnershipMismatchError(
                "Database belongs to another Discord application. "
                f"Expected application_id={current_owner}, "
                f"received application_id={application_id}."
            )
