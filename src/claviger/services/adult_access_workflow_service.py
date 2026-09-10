from collections.abc import Iterable

from claviger.models.adult_access import AdultAccess
from claviger.models.adult_access_theme_model import (
    AdultAccessTheme,
)
from claviger.services.catalog_variant_classifier import (
    CatalogVariantClassifier,
)


class AdultAccessWorkflowService:
    """Build logical user choices from technical adult-access entries."""

    def __init__(
        self,
        classifier: CatalogVariantClassifier | None = None,
    ) -> None:
        self.classifier = (
            classifier if classifier is not None else CatalogVariantClassifier()
        )

    def build_themes(
        self,
        accesses: Iterable[AdultAccess],
    ) -> tuple[AdultAccessTheme, ...]:
        """Build paired questionnaire themes from publicly ready accesses."""

        ready_accesses = tuple(
            access for access in accesses if access.is_publicly_ready
        )

        classification = self.classifier.classify(
            access.access_key for access in ready_accesses
        )

        access_by_key: dict[str, AdultAccess] = {}

        for access in ready_accesses:
            access_by_key.setdefault(
                access.access_key,
                access,
            )

        duplicate_keys = set(
            classification.duplicate_keys,
        )

        themes: list[AdultAccessTheme] = []

        for pair in classification.pairs:
            if pair.no_ai_key in duplicate_keys or pair.ai_key in duplicate_keys:
                continue

            base_access = access_by_key[pair.no_ai_key]
            ai_access = access_by_key[pair.ai_key]

            themes.append(
                AdultAccessTheme(
                    theme_key=pair.theme_key,
                    base_access=base_access,
                    ai_access=ai_access,
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
            unknown_key = sorted(
                unknown_keys,
            )[0]

            raise ValueError(f"Unknown adult access theme: {unknown_key!r}.")

        role_ids: list[int] = []

        for theme in themes:
            if theme.theme_key not in selected_keys:
                continue

            role_ids.append(
                theme.base_access.role_id,
            )

            if include_ai and theme.ai_access is not None:
                role_ids.append(
                    theme.ai_access.role_id,
                )

        return tuple(role_ids)
