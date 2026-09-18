from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowRoleExecutionResult:
    """Describe role mutations actually applied by a generic workflow."""

    added_role_ids: tuple[int, ...] = ()
    removed_role_ids: tuple[int, ...] = ()

    @property
    def change_count(self) -> int:
        """Return the total number of Discord role mutations applied."""

        return len(self.added_role_ids) + len(self.removed_role_ids)

    @property
    def has_changes(self) -> bool:
        """Return whether Discord member roles changed."""

        return self.change_count > 0
