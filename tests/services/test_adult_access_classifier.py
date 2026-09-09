from claviger.services.adult_access_classifier import (
    AdultAccessClassifier,
)


def test_classifier_identifies_all_supported_access_shapes() -> None:
    """Classify paired, solo, IA-only and no-IA-only accesses."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "no-ia-test",
            "ia-test",
            "test",
            "ia-solo",
            "no-ia-single",
        )
    )

    assert len(classification.pairs) == 1

    pair = classification.pairs[0]

    assert pair.theme_key == "test"
    assert pair.no_ai_key == "no-ia-test"
    assert pair.ai_key == "ia-test"

    assert classification.solo_keys == ("test",)

    assert classification.ai_only_keys == ("ia-solo",)

    assert classification.no_ai_only_keys == ("no-ia-single",)

    assert classification.invalid_keys == ()
    assert classification.duplicate_keys == ()


def test_classifier_is_independent_from_input_order() -> None:
    """Produce deterministic classification regardless of discovery order."""

    classifier = AdultAccessClassifier()

    first = classifier.classify(
        (
            "no-ia-zeta",
            "ia-zeta",
            "alpha",
            "ia-beta",
        )
    )

    second = classifier.classify(
        (
            "ia-beta",
            "alpha",
            "ia-zeta",
            "no-ia-zeta",
        )
    )

    assert first == second


def test_classifier_builds_multiple_pairs_in_canonical_order() -> None:
    """Sort logical pairs by their theme key."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "ia-zeta",
            "no-ia-alpha",
            "no-ia-zeta",
            "ia-alpha",
        )
    )

    assert tuple(pair.theme_key for pair in classification.pairs) == (
        "alpha",
        "zeta",
    )


def test_classifier_keeps_prefixed_variants_without_siblings_visible() -> None:
    """Expose incomplete prefixed accesses instead of silently dropping them."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "ia-ai-only",
            "no-ia-base-only",
        )
    )

    assert classification.pairs == ()

    assert classification.ai_only_keys == ("ia-ai-only",)

    assert classification.no_ai_only_keys == ("no-ia-base-only",)


def test_classifier_rejects_empty_prefixed_theme_keys() -> None:
    """Expose malformed IA prefixes as invalid configuration."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "",
            "   ",
            "ia-",
            "no-ia-",
            "valid",
        )
    )

    assert classification.solo_keys == ("valid",)

    assert classification.invalid_keys == (
        "",
        "",
        "ia-",
        "no-ia-",
    )


def test_classifier_reports_duplicate_keys_without_duplicate_results() -> None:
    """Report duplicate technical keys while classifying them only once."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "no-ia-test",
            "no-ia-test",
            "ia-test",
            "ia-test",
            "solo",
            "solo",
        )
    )

    assert len(classification.pairs) == 1

    assert classification.solo_keys == ("solo",)

    assert classification.duplicate_keys == (
        "ia-test",
        "no-ia-test",
        "solo",
    )


def test_similar_names_without_exact_prefix_are_solo_accesses() -> None:
    """Only exact IA prefixes carry IA semantics."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(
        (
            "iax-test",
            "no-iax-test",
        )
    )

    assert classification.solo_keys == (
        "iax-test",
        "no-iax-test",
    )

    assert classification.pairs == ()
    assert classification.ai_only_keys == ()
    assert classification.no_ai_only_keys == ()


def test_classifier_accepts_empty_catalog() -> None:
    """Return an empty classification for an empty adult-access catalog."""

    classifier = AdultAccessClassifier()

    classification = classifier.classify(())

    assert classification.pairs == ()
    assert classification.solo_keys == ()
    assert classification.ai_only_keys == ()
    assert classification.no_ai_only_keys == ()
    assert classification.invalid_keys == ()
    assert classification.duplicate_keys == ()
