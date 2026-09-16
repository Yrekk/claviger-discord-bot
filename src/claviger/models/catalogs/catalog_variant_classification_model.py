from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CatalogVariantPair:
    """Represent one logical no-AI / AI catalog variant pair."""

    theme_key: str
    no_ai_key: str
    ai_key: str


@dataclass(frozen=True, slots=True)
class CatalogVariantClassification:
    """Represent AI-variant semantics found inside one catalog."""

    pairs: tuple[CatalogVariantPair, ...]
    solo_keys: tuple[str, ...]
    ai_only_keys: tuple[str, ...]
    no_ai_only_keys: tuple[str, ...]
    invalid_keys: tuple[str, ...]
    duplicate_keys: tuple[str, ...]
