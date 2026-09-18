from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkflowRolePlan:
    """Describe role mutations required by one generic workflow submission."""

    add_role_ids: tuple[int, ...] = ()
    remove_role_ids: tuple[int, ...] = ()

    @property
    def change_count(self) -> int:
        """Return the total number of planned Discord role mutations."""

        return len(self.add_role_ids) + len(self.remove_role_ids)

    @property
    def has_changes(self) -> bool:
        """Return whether the member requires at least one role mutation."""

        return self.change_count > 0
