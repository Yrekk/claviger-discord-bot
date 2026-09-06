from dataclasses import dataclass

from claviger.models.adult_access import AdultAccess


@dataclass(frozen=True)
class AdultAccessTheme:
    """Represent one logical adult-access theme."""

    theme_key: str
    base_access: AdultAccess
    ai_access: AdultAccess | None

    @property
    def label(self) -> str:
        """Return the human-facing theme label."""

        if self.base_access.label is None:
            raise ValueError(f"Adult access theme {self.theme_key!r} has no label.")

        return self.base_access.label

    @property
    def description(self) -> str:
        """Return the human-facing theme description."""

        if self.base_access.description is None:
            raise ValueError(
                f"Adult access theme {self.theme_key!r} has no description."
            )

        return self.base_access.description

    @property
    def emoji(self) -> str | None:
        """Return the human-facing theme emoji."""

        return self.base_access.emoji
