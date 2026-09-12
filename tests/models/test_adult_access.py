from claviger.models.adult_access import AdultAccess


def create_access(
    *,
    label: str | None = "IA adulte",
    description: str | None = "Accès au contenu IA adulte.",
    enabled: bool = True,
    discord_present: bool = True,
    role_manageable: bool = True,
    channel_present: bool = True,
    mapping_valid: bool = True,
    matches_policy: bool = True,
) -> AdultAccess:
    """Create an adult access for domain model tests."""

    return AdultAccess(
        guild_id=123,
        role_id=456,
        role_name="access-ia-futa",
        catalog_key="ia-futa",
        channel_id=789,
        channel_name="ia-futa",
        label=label,
        description=description,
        emoji="🔞",
        sort_order=10,
        enabled=enabled,
        discord_present=discord_present,
        role_manageable=role_manageable,
        channel_present=channel_present,
        mapping_valid=mapping_valid,
        matches_policy=matches_policy,
    )


def test_adult_access_exposes_access_key_alias() -> None:
    """Keep adult access terminology while sharing the generic catalog model."""

    access = create_access()

    assert access.catalog_key == "ia-futa"
    assert access.access_key == "ia-futa"


def test_adult_access_inherits_public_readiness_rules() -> None:
    """Use the shared catalog availability rules for adult access."""

    access = create_access(
        mapping_valid=False,
    )

    assert access.is_available is False
    assert access.is_publicly_ready is False
