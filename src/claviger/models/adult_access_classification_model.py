from dataclasses import dataclass


@dataclass(frozen=True)
class AdultAccessPair:
    """Represent one logical no-IA / IA adult-access pair."""

    theme_key: str
    no_ai_key: str
    ai_key: str


@dataclass(frozen=True)
class AdultAccessClassification:
    """Represent the semantic classification of adult-access catalog keys."""

    pairs: tuple[AdultAccessPair, ...]
    solo_keys: tuple[str, ...]
    ai_only_keys: tuple[str, ...]
    no_ai_only_keys: tuple[str, ...]
    invalid_keys: tuple[str, ...]
    duplicate_keys: tuple[str, ...]
