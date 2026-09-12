import pytest

from claviger.policies.default_policy import (
    SAFE_DEFAULT_POLICY,
    SUCCUMBRAE_FALLBACK_POLICY,
)


def test_safe_default_policy_disables_sensitive_role_features() -> None:
    """Keep role-related features disabled in the generic safe fallback."""
    assert SAFE_DEFAULT_POLICY.role_management_enabled is False
    assert SAFE_DEFAULT_POLICY.adult_access_enabled is False


def test_succumbrae_fallback_keeps_role_features_enabled() -> None:
    """Keep essential role flows available on Succumbrae without the database."""
    assert SUCCUMBRAE_FALLBACK_POLICY.role_management_enabled is True
    assert SUCCUMBRAE_FALLBACK_POLICY.adult_access_enabled is True


def test_succumbrae_fallback_uses_expected_role_conventions() -> None:
    """Use Succumbrae's known role naming conventions."""
    assert SUCCUMBRAE_FALLBACK_POLICY.member_role_name == "Membre"
    assert SUCCUMBRAE_FALLBACK_POLICY.adult_role_name == "Civis Noctis - 18+"
    assert SUCCUMBRAE_FALLBACK_POLICY.adult_access_prefix == "access-"


def test_succumbrae_fallback_uses_expected_flow_channels() -> None:
    """Use the known channels required by Succumbrae's membership flows."""
    assert SUCCUMBRAE_FALLBACK_POLICY.salutations_channel_name == "salutationes"
    assert SUCCUMBRAE_FALLBACK_POLICY.adult_access_channel_name == "aditus-noctis"


def test_policy_is_immutable() -> None:
    """Prevent accidental mutation of a loaded guild policy."""
    with pytest.raises(AttributeError):
        SUCCUMBRAE_FALLBACK_POLICY.member_role_name = "Autre rôle"
