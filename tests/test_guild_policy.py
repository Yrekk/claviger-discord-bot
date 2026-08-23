from dataclasses import FrozenInstanceError

import pytest

from claviger.policies.guild_policy import (
    GuildPolicy,
    GuildPolicyOverrides,
)


def test_policy_overrides_are_empty_by_default() -> None:
    """Leave every policy setting untouched when no override is configured."""
    overrides = GuildPolicyOverrides()

    assert overrides.member_role_name is None
    assert overrides.adult_role_name is None

    assert overrides.member_interest_prefix is None
    assert overrides.adult_access_prefix is None

    assert overrides.salutations_channel_name is None
    assert overrides.adult_rules_channel_name is None

    assert overrides.role_management_enabled is None
    assert overrides.adult_access_enabled is None


def test_policy_overrides_can_store_partial_configuration() -> None:
    """Allow a guild to override only selected policy settings."""
    overrides = GuildPolicyOverrides(
        adult_role_name="Accès adulte",
        member_interest_prefix="topic-",
        adult_access_prefix="private-",
        adult_access_enabled=True,
    )

    assert overrides.adult_role_name == "Accès adulte"
    assert overrides.member_interest_prefix == "topic-"
    assert overrides.adult_access_prefix == "private-"
    assert overrides.adult_access_enabled is True

    assert overrides.member_role_name is None
    assert overrides.role_management_enabled is None


def test_policy_overrides_are_immutable() -> None:
    """Prevent accidental mutation of loaded policy overrides."""
    overrides = GuildPolicyOverrides()

    with pytest.raises(FrozenInstanceError):
        setattr(
            overrides,
            "member_role_name",
            "Autre rôle",
        )


def test_effective_policy_is_immutable() -> None:
    """Prevent accidental mutation of an effective guild policy."""
    policy = GuildPolicy(
        member_role_name="Membre",
        adult_role_name="Adulte (18+)",
        member_interest_prefix="interest-",
        adult_access_prefix="access-",
        salutations_channel_name="salutations",
        adult_rules_channel_name="adult-rules",
        role_management_enabled=False,
        adult_access_enabled=False,
    )

    with pytest.raises(FrozenInstanceError):
        setattr(
            policy,
            "member_role_name",
            "Autre rôle",
        )