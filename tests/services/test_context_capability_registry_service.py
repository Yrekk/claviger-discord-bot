import pytest

from claviger.models.context_capability_model import ContextCapability
from claviger.services.context_capability_registry_service import (
    ContextCapabilityRegistry,
    DuplicateContextCapabilityError,
)


def test_default_registry_contains_ai_preference() -> None:
    """Expose the AI preference capability implemented by the engine."""

    registry = ContextCapabilityRegistry()

    capability = registry.get(
        "ai_preference",
    )

    assert capability == ContextCapability(
        capability_key="ai_preference",
        value_type="boolean",
    )


def test_registry_returns_none_for_unknown_capability() -> None:
    """Return None when the engine does not implement a capability."""

    registry = ContextCapabilityRegistry()

    assert registry.get("missing-capability") is None

    assert registry.contains("missing-capability") is False


def test_registry_accepts_explicit_capabilities() -> None:
    """Allow engine composition to provide another capability set."""

    registry = ContextCapabilityRegistry(
        (
            ContextCapability(
                capability_key="test_preference",
                value_type="boolean",
            ),
        )
    )

    assert registry.contains("test_preference") is True

    assert registry.contains("ai_preference") is False


def test_registry_rejects_duplicate_capability_keys() -> None:
    """Reject ambiguous engine capability registrations."""

    capability = ContextCapability(
        capability_key="test_preference",
        value_type="boolean",
    )

    with pytest.raises(
        DuplicateContextCapabilityError,
        match="test_preference",
    ):
        ContextCapabilityRegistry(
            (
                capability,
                capability,
            )
        )
