import pytest

from claviger.models.adult_access import AdultAccess
from claviger.services.adult_access_classifier import (
    AdultAccessClassifier,
)
from claviger.services.adult_access_workflow_service import (
    AdultAccessWorkflowService,
)


def create_access(
    *,
    role_id: int,
    access_key: str,
    label: str | None = "Theme",
    description: str | None = "Description",
    sort_order: int = 10,
    enabled: bool = True,
    discord_present: bool = True,
    role_manageable: bool = True,
    channel_present: bool = True,
    mapping_valid: bool = True,
    matches_policy: bool = True,
) -> AdultAccess:
    """Create an adult-access catalog entry."""

    return AdultAccess(
        guild_id=123,
        role_id=role_id,
        role_name=f"access-{access_key}",
        catalog_key=access_key,
        channel_id=role_id + 1000,
        channel_name=access_key,
        label=label,
        description=description,
        emoji=None,
        sort_order=sort_order,
        enabled=enabled,
        discord_present=discord_present,
        role_manageable=role_manageable,
        channel_present=channel_present,
        mapping_valid=mapping_valid,
        matches_policy=matches_policy,
    )


def create_service() -> AdultAccessWorkflowService:
    """Create the adult-access workflow service."""

    return AdultAccessWorkflowService(
        classifier=AdultAccessClassifier(),
    )


def test_build_themes_uses_paired_accesses() -> None:
    """Build one logical theme from its no-IA and IA variants."""

    service = create_service()

    no_ai_access = create_access(
        role_id=10,
        access_key="no-ia-casino",
        label="Casino",
    )

    ai_access = create_access(
        role_id=11,
        access_key="ia-casino",
        label="Casino IA",
    )

    themes = service.build_themes(
        (
            ai_access,
            no_ai_access,
        )
    )

    assert len(themes) == 1

    theme = themes[0]

    assert theme.theme_key == "casino"
    assert theme.base_access is no_ai_access
    assert theme.ai_access is ai_access
    assert theme.label == "Casino"


def test_build_themes_excludes_non_pair_shapes() -> None:
    """Do not expose incomplete or additional access shapes as pair themes."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-incomplete",
            ),
            create_access(
                role_id=20,
                access_key="ia-ai-only",
            ),
            create_access(
                role_id=30,
                access_key="solo",
            ),
        )
    )

    assert themes == ()


def test_build_themes_requires_both_variants_to_be_publicly_ready() -> None:
    """Exclude a pair when one of its variants is not publicly ready."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-casino",
            ),
            create_access(
                role_id=11,
                access_key="ia-casino",
                channel_present=False,
            ),
        )
    )

    assert themes == ()


def test_build_themes_orders_pairs_by_base_sort_order() -> None:
    """Order paired themes using the no-IA catalog entry."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-casino",
                sort_order=20,
            ),
            create_access(
                role_id=11,
                access_key="ia-casino",
                sort_order=20,
            ),
            create_access(
                role_id=20,
                access_key="no-ia-poker",
                sort_order=10,
            ),
            create_access(
                role_id=21,
                access_key="ia-poker",
                sort_order=10,
            ),
        )
    )

    assert tuple(theme.theme_key for theme in themes) == (
        "poker",
        "casino",
    )


def test_build_themes_excludes_ambiguous_duplicate_keys() -> None:
    """Do not expose a pair containing a duplicated catalog key."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-casino",
            ),
            create_access(
                role_id=12,
                access_key="no-ia-casino",
            ),
            create_access(
                role_id=11,
                access_key="ia-casino",
            ),
        )
    )

    assert themes == ()


def test_resolve_role_ids_adds_ai_variants_when_requested() -> None:
    """Resolve selected pair roles in canonical questionnaire order."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-casino",
                sort_order=20,
            ),
            create_access(
                role_id=11,
                access_key="ia-casino",
                sort_order=20,
            ),
            create_access(
                role_id=20,
                access_key="no-ia-poker",
                sort_order=10,
            ),
            create_access(
                role_id=21,
                access_key="ia-poker",
                sort_order=10,
            ),
        )
    )

    assert service.resolve_role_ids(
        themes,
        (
            "casino",
            "poker",
        ),
        include_ai=False,
    ) == (
        20,
        10,
    )

    assert service.resolve_role_ids(
        themes,
        (
            "casino",
            "poker",
        ),
        include_ai=True,
    ) == (
        20,
        21,
        10,
        11,
    )


def test_resolve_role_ids_rejects_unknown_theme() -> None:
    """Reject a selection that is not part of the questionnaire."""

    service = create_service()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-casino",
            ),
            create_access(
                role_id=11,
                access_key="ia-casino",
            ),
        )
    )

    with pytest.raises(
        ValueError,
        match="Unknown adult access theme",
    ):
        service.resolve_role_ids(
            themes,
            ("unknown",),
            include_ai=True,
        )
