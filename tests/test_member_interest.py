from claviger.models.member_interest import MemberInterest


def create_interest(
    *,
    label: str | None = "Jeux vidéo",
    description: str | None = "Discussions autour des jeux vidéo.",
    enabled: bool = True,
    discord_present: bool = True,
    role_manageable: bool = True,
    channel_present: bool = True,
    mapping_valid: bool = True,
    matches_policy: bool = True,
) -> MemberInterest:
    """Create a member interest for domain model tests."""

    return MemberInterest(
        guild_id=123,
        role_id=456,
        role_name="interest-ludus",
        interest_key="ludus",
        channel_id=789,
        channel_name="ludus",
        label=label,
        description=description,
        emoji="🎮",
        sort_order=10,
        enabled=enabled,
        discord_present=discord_present,
        role_manageable=role_manageable,
        channel_present=channel_present,
        mapping_valid=mapping_valid,
        matches_policy=matches_policy,
    )


def test_member_interest_is_configured_with_required_metadata() -> None:
    """Consider label and description sufficient human configuration."""

    interest = create_interest()

    assert interest.is_configured is True


def test_member_interest_is_not_configured_when_label_is_missing() -> None:
    """Treat a missing label as incomplete configuration."""

    interest = create_interest(
        label=None,
    )

    assert interest.is_configured is False


def test_member_interest_accepts_intentionally_empty_description() -> None:
    """Distinguish an intentionally empty description from NULL."""

    interest = create_interest(
        description="",
    )

    assert interest.is_configured is True


def test_member_interest_requires_valid_discord_state_to_be_available() -> None:
    """Hide interests whose Discord mapping is no longer valid."""

    interest = create_interest(
        channel_present=False,
    )

    assert interest.is_available is False
    assert interest.is_publicly_ready is False


def test_member_interest_is_publicly_ready_when_complete_and_available() -> None:
    """Expose only fully configured and currently usable interests."""

    interest = create_interest()

    assert interest.is_publicly_ready is True


def test_member_interest_requires_valid_role_channel_mapping() -> None:
    """Hide interests whose role-to-channel mapping is ambiguous."""

    interest = create_interest(
        mapping_valid=False,
    )

    assert interest.is_available is False
    assert interest.is_publicly_ready is False


def test_member_interest_requires_manageable_role() -> None:
    """Hide interests whose Discord role cannot be managed by Claviger."""

    interest = create_interest(
        role_manageable=False,
    )

    assert interest.is_available is False
    assert interest.is_publicly_ready is False
