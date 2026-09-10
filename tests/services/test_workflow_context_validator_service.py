import pytest

from claviger.models.context_capability_model import ContextCapability
from claviger.models.context_definition_model import ContextDefinition
from claviger.models.resolved_context_model import ResolvedContext
from claviger.models.workflow_definition_model import (
    WorkflowContextBinding,
)
from claviger.services.context_capability_registry_service import (
    ContextCapabilityRegistry,
)
from claviger.services.workflow_context_validator_service import (
    ContextCapabilityTypeMismatchError,
    ContextNotManageableError,
    UnsupportedContextCapabilityError,
    WorkflowContextValidator,
)


def create_resolved_context(
    *,
    capability_key: str = "ai_preference",
    value_type: str = "boolean",
    interaction_mode: str = "editable",
    context_enabled: bool = True,
    binding_enabled: bool = True,
    role_manageable: bool = True,
) -> ResolvedContext:
    """Create one resolved context for validation tests."""

    binding = WorkflowContextBinding(
        context=ContextDefinition(
            guild_id=123,
            context_key="test-context",
            capability_key=capability_key,
            value_type=value_type,  # type: ignore[arg-type]
            role_id=111,
            label="Test context",
            description=None,
            sort_order=0,
            enabled=context_enabled,
        ),
        interaction_mode=interaction_mode,  # type: ignore[arg-type]
        sort_order=0,
        enabled=binding_enabled,
    )

    return ResolvedContext(
        binding=binding,
        current_value=False,
        role_manageable=role_manageable,
    )


def create_validator(
    *capabilities: ContextCapability,
) -> WorkflowContextValidator:
    """Create a validator with deterministic engine capabilities."""

    registry = ContextCapabilityRegistry(
        capabilities
        or (
            ContextCapability(
                capability_key="ai_preference",
                value_type="boolean",
            ),
        )
    )

    return WorkflowContextValidator(
        registry,
    )


def test_validate_accepts_supported_editable_context() -> None:
    """Accept a supported editable context with a manageable role."""

    validator = create_validator()

    validator.validate((create_resolved_context(),))


def test_validate_accepts_supported_read_only_context() -> None:
    """Allow read-only contexts whose role cannot be managed."""

    validator = create_validator()

    validator.validate(
        (
            create_resolved_context(
                interaction_mode="read_only",
                role_manageable=False,
            ),
        )
    )


def test_validate_rejects_unknown_active_capability() -> None:
    """Fail closed when active configuration references unknown behavior."""

    validator = create_validator()

    with pytest.raises(
        UnsupportedContextCapabilityError,
        match="unknown_capability",
    ):
        validator.validate(
            (
                create_resolved_context(
                    capability_key="unknown_capability",
                ),
            )
        )


def test_validate_ignores_unknown_disabled_context() -> None:
    """Allow unsupported dormant context definitions to remain persisted."""

    validator = create_validator()

    validator.validate(
        (
            create_resolved_context(
                capability_key="unknown_capability",
                context_enabled=False,
            ),
        )
    )


def test_validate_ignores_unknown_disabled_binding() -> None:
    """Allow unsupported dormant workflow bindings to remain persisted."""

    validator = create_validator()

    validator.validate(
        (
            create_resolved_context(
                capability_key="unknown_capability",
                binding_enabled=False,
            ),
        )
    )


def test_validate_rejects_capability_value_type_mismatch() -> None:
    """Reject contexts whose persisted type conflicts with engine metadata."""

    validator = create_validator(
        ContextCapability(
            capability_key="test_capability",
            value_type="boolean",
        )
    )

    with pytest.raises(
        ContextCapabilityTypeMismatchError,
        match="test_capability",
    ):
        validator.validate(
            (
                create_resolved_context(
                    capability_key="test_capability",
                    value_type="text",
                ),
            )
        )


def test_validate_rejects_unmanageable_editable_context() -> None:
    """Fail before planning when an editable role cannot be managed."""

    validator = create_validator()

    with pytest.raises(
        ContextNotManageableError,
        match="111",
    ):
        validator.validate(
            (
                create_resolved_context(
                    role_manageable=False,
                ),
            )
        )


def test_validate_checks_every_active_context() -> None:
    """Do not stop validating after an earlier valid context."""

    validator = create_validator()

    contexts = (
        create_resolved_context(),
        create_resolved_context(
            capability_key="unknown_capability",
        ),
    )

    with pytest.raises(
        UnsupportedContextCapabilityError,
        match="unknown_capability",
    ):
        validator.validate(
            contexts,
        )
