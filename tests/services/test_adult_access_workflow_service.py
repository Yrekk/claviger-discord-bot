import pytest

from claviger.models.adult_access import AdultAccess
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


def test_build_themes_uses_no_ai_access_as_reference() -> None:
    """Build one logical theme from its no-IA and IA variants."""

    service = AdultAccessWorkflowService()

    base = create_access(
        role_id=10,
        access_key="no-ia-yuri",
        label="Yuri",
    )

    ai = create_access(
        role_id=11,
        access_key="ia-yuri",
        label="Yuri IA",
    )

    themes = service.build_themes(
        (
            ai,
            base,
        )
    )

    assert len(themes) == 1

    theme = themes[0]

    assert theme.theme_key == "yuri"
    assert theme.base_access is base
    assert theme.ai_access is ai
    assert theme.label == "Yuri"


def test_build_themes_keeps_base_without_ai_variant() -> None:
    """Keep a valid base theme when no IA variant exists."""

    service = AdultAccessWorkflowService()

    base = create_access(
        role_id=10,
        access_key="no-ia-yuri",
    )

    themes = service.build_themes((base,))

    assert len(themes) == 1
    assert themes[0].theme_key == "yuri"
    assert themes[0].ai_access is None


def test_build_themes_ignores_unavailable_entries() -> None:
    """Ignore unavailable bases and unavailable IA variants."""

    service = AdultAccessWorkflowService()

    unavailable_base = create_access(
        role_id=10,
        access_key="no-ia-yuri",
        enabled=False,
    )

    valid_base = create_access(
        role_id=20,
        access_key="no-ia-bdsm",
        label="Shibari - BDSM",
    )

    unavailable_ai = create_access(
        role_id=21,
        access_key="ia-bdsm",
        channel_present=False,
    )

    themes = service.build_themes(
        (
            unavailable_base,
            valid_base,
            unavailable_ai,
        )
    )

    assert len(themes) == 1
    assert themes[0].theme_key == "bdsm"
    assert themes[0].ai_access is None


def test_resolve_role_ids_adds_ai_variants_when_requested() -> None:
    """Add IA roles in addition to every selected base role."""

    service = AdultAccessWorkflowService()

    themes = service.build_themes(
        (
            create_access(
                role_id=10,
                access_key="no-ia-yuri",
            ),
            create_access(
                role_id=11,
                access_key="ia-yuri",
            ),
            create_access(
                role_id=20,
                access_key="no-ia-bdsm",
            ),
            create_access(
                role_id=21,
                access_key="ia-bdsm",
            ),
        )
    )

    assert service.resolve_role_ids(
        themes,
        (
            "yuri",
            "bdsm",
        ),
        include_ai=False,
    ) == (
        20,
        10,
    )

    assert service.resolve_role_ids(
        themes,
        (
            "yuri",
            "bdsm",
        ),
        include_ai=True,
    ) == (
        20,
        21,
        10,
        11,
    )

    with pytest.raises(
        ValueError,
        match="unknown",
    ):
        service.resolve_role_ids(
            themes,
            ("unknown",),
            include_ai=True,
        )
