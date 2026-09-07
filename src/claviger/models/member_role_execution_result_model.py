from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemberRoleExecutionResult:
    """Describe the Discord role changes actually applied by /membre."""

    added_role_ids: tuple[int, ...] = ()
    removed_role_ids: tuple[int, ...] = ()

    @property
    def change_count(self) -> int:
        """Return the number of Discord role mutations actually applied."""

        return len(self.added_role_ids) + len(self.removed_role_ids)

    @property
    def has_changes(self) -> bool:
        """Return whether at least one Discord role was actually changed."""

        return self.change_count > 0
