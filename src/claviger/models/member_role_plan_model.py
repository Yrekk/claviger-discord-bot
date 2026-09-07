from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemberRolePlan:
    """Describe the Discord role changes required by /membre."""

    add_role_ids: tuple[int, ...] = ()
    remove_role_ids: tuple[int, ...] = ()

    @property
    def change_count(self) -> int:
        """Return the number of planned Discord role mutations."""

        return len(self.add_role_ids) + len(self.remove_role_ids)

    @property
    def has_changes(self) -> bool:
        """Return whether at least one Discord role must change."""

        return self.change_count > 0
