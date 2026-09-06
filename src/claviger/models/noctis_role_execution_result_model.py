from dataclasses import dataclass


@dataclass(frozen=True)
class NoctisRoleExecutionResult:
    """Describe the role changes actually applied to a member."""

    added_role_ids: tuple[int, ...]
    removed_role_ids: tuple[int, ...]

    @property
    def change_count(self) -> int:
        """Return the number of role changes actually applied."""

        return len(self.added_role_ids) + len(self.removed_role_ids)
