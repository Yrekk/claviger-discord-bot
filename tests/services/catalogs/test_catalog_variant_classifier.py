from claviger.models.catalog_variant_classification_model import (
    CatalogVariantClassification,
    CatalogVariantPair,
)
from claviger.services.catalog_variant_classifier import (
    CatalogVariantClassifier,
)


def test_classifier_builds_generic_catalog_variant_shapes() -> None:
    """Classify AI semantics independently from any business catalog."""

    classifier = CatalogVariantClassifier()

    result = classifier.classify(
        (
            "no-ia-casino",
            "ia-casino",
            "gaming",
            "ia-studio",
            "no-ia-archive",
        )
    )

    assert result == CatalogVariantClassification(
        pairs=(
            CatalogVariantPair(
                theme_key="casino",
                no_ai_key="no-ia-casino",
                ai_key="ia-casino",
            ),
        ),
        solo_keys=("gaming",),
        ai_only_keys=("ia-studio",),
        no_ai_only_keys=("no-ia-archive",),
        invalid_keys=(),
        duplicate_keys=(),
    )


def test_classifier_is_independent_from_catalog_family() -> None:
    """Apply identical variant semantics to keys from any catalog family."""

    classifier = CatalogVariantClassifier()

    first = classifier.classify(
        (
            "no-ia-art",
            "ia-art",
        )
    )

    second = classifier.classify(
        (
            "no-ia-art",
            "ia-art",
        )
    )

    assert first == second
    assert first.pairs[0].theme_key == "art"


def test_classifier_reports_duplicates_generically() -> None:
    """Preserve duplicate detection outside the legacy adult workflow."""

    classifier = CatalogVariantClassifier()

    result = classifier.classify(
        (
            "ia-casino",
            "ia-casino",
            "no-ia-casino",
        )
    )

    assert result.duplicate_keys == ("ia-casino",)

    assert len(result.pairs) == 1
