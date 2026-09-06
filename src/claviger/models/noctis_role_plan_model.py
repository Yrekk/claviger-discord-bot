from dataclasses import dataclass


@dataclass(frozen=True)
class NoctisRolePlan:
    """Describe the Discord role changes required by /noctis."""

    add_role_ids: tuple[int, ...]
    remove_role_ids: tuple[int, ...]

    @property
    def change_count(self) -> int:
        """Return the total number of role changes."""

        return len(self.add_role_ids) + len(self.remove_role_ids)

    @property
    def has_changes(self) -> bool:
        """Return whether the member requires any role change."""

        return self.change_count > 0
