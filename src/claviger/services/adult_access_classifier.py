from collections import Counter
from collections.abc import Iterable

from claviger.models.adult_access_classification_model import (
    AdultAccessClassification,
    AdultAccessPair,
)


class AdultAccessClassifier:
    """Classify adult-access keys according to their IA semantics."""

    NO_AI_PREFIX = "no-ia-"
    AI_PREFIX = "ia-"

    def classify(
        self,
        access_keys: Iterable[str],
    ) -> AdultAccessClassification:
        """Classify adult-access keys into pair, solo and incomplete variants."""

        normalized_keys = tuple(key.strip() for key in access_keys)

        valid_keys: list[str] = []
        invalid_keys: list[str] = []

        for key in normalized_keys:
            if not key:
                invalid_keys.append(key)
                continue

            if key == self.NO_AI_PREFIX:
                invalid_keys.append(key)
                continue

            if key == self.AI_PREFIX:
                invalid_keys.append(key)
                continue

            valid_keys.append(key)

        counts = Counter(
            valid_keys,
        )

        duplicate_keys = tuple(
            sorted(key for key, count in counts.items() if count > 1)
        )

        unique_keys = set(
            valid_keys,
        )

        no_ai_by_theme = {
            self._extract_theme_key(
                key,
                prefix=self.NO_AI_PREFIX,
            ): key
            for key in unique_keys
            if key.startswith(self.NO_AI_PREFIX)
        }

        ai_by_theme = {
            self._extract_theme_key(
                key,
                prefix=self.AI_PREFIX,
            ): key
            for key in unique_keys
            if key.startswith(self.AI_PREFIX)
        }

        paired_theme_keys = no_ai_by_theme.keys() & ai_by_theme.keys()

        pairs = tuple(
            AdultAccessPair(
                theme_key=theme_key,
                no_ai_key=no_ai_by_theme[theme_key],
                ai_key=ai_by_theme[theme_key],
            )
            for theme_key in sorted(
                paired_theme_keys,
            )
        )

        ai_only_keys = tuple(
            ai_by_theme[theme_key]
            for theme_key in sorted(ai_by_theme.keys() - no_ai_by_theme.keys())
        )

        no_ai_only_keys = tuple(
            no_ai_by_theme[theme_key]
            for theme_key in sorted(no_ai_by_theme.keys() - ai_by_theme.keys())
        )

        solo_keys = tuple(
            sorted(
                key
                for key in unique_keys
                if not key.startswith(
                    (
                        self.NO_AI_PREFIX,
                        self.AI_PREFIX,
                    )
                )
            )
        )

        return AdultAccessClassification(
            pairs=pairs,
            solo_keys=solo_keys,
            ai_only_keys=ai_only_keys,
            no_ai_only_keys=no_ai_only_keys,
            invalid_keys=tuple(
                sorted(
                    invalid_keys,
                )
            ),
            duplicate_keys=duplicate_keys,
        )

    @staticmethod
    def _extract_theme_key(
        access_key: str,
        *,
        prefix: str,
    ) -> str:
        """Return the logical theme represented by one prefixed access key."""

        theme_key = access_key.removeprefix(
            prefix,
        )

        if not theme_key:
            raise ValueError(f"Invalid adult access key: {access_key!r}.")

        return theme_key
