from collections.abc import Iterable

from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_theme_model import (
    AdultAccessTheme,
)


class AdultAccessWorkflowService:
    """Build logical user choices from technical adult-access entries."""

    BASE_PREFIX = "no-ia-"
    AI_PREFIX = "ia-"

    def build_themes(
        self,
        accesses: Iterable[AdultAccess],
    ) -> tuple[AdultAccessTheme, ...]:
        """Build questionnaire themes from available no-IA accesses."""

        entries = tuple(accesses)

        ai_by_theme = {
            self._extract_theme_key(
                access.access_key,
                prefix=self.AI_PREFIX,
            ): access
            for access in entries
            if (
                access.access_key.startswith(self.AI_PREFIX)
                and access.is_publicly_ready
            )
        }

        themes: list[AdultAccessTheme] = []

        for access in entries:
            if not access.access_key.startswith(self.BASE_PREFIX):
                continue

            if not access.is_publicly_ready:
                continue

            theme_key = self._extract_theme_key(
                access.access_key,
                prefix=self.BASE_PREFIX,
            )

            themes.append(
                AdultAccessTheme(
                    theme_key=theme_key,
                    base_access=access,
                    ai_access=ai_by_theme.get(theme_key),
                )
            )

        themes.sort(
            key=lambda theme: (
                theme.base_access.sort_order,
                theme.theme_key,
            )
        )

        return tuple(themes)

    def resolve_role_ids(
        self,
        themes: Iterable[AdultAccessTheme],
        selected_theme_keys: Iterable[str],
        *,
        include_ai: bool,
    ) -> tuple[int, ...]:
        """Resolve Discord role IDs in canonical catalog order."""

        themes = tuple(themes)
        selected_keys = set(selected_theme_keys)

        known_keys = {theme.theme_key for theme in themes}

        unknown_keys = selected_keys - known_keys

        if unknown_keys:
            unknown_key = sorted(unknown_keys)[0]

            raise ValueError(f"Unknown adult access theme: {unknown_key!r}.")

        role_ids: list[int] = []

        for theme in themes:
            if theme.theme_key not in selected_keys:
                continue

            role_ids.append(theme.base_access.role_id)

            if include_ai and theme.ai_access is not None:
                role_ids.append(theme.ai_access.role_id)

        return tuple(role_ids)

    @staticmethod
    def _extract_theme_key(
        access_key: str,
        *,
        prefix: str,
    ) -> str:
        """Extract and validate the logical theme key."""

        theme_key = access_key.removeprefix(
            prefix,
        )

        if not theme_key:
            raise ValueError(f"Invalid adult access key: {access_key!r}.")

        return theme_key
