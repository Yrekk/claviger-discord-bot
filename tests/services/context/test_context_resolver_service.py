from unittest.mock import Mock

import discord
import pytest

from claviger.models.context_definition_model import ContextDefinition
from claviger.models.workflow_definition_model import (
    WorkflowContextBinding,
    WorkflowDefinition,
)
from claviger.services.context_resolver_service import (
    ContextGuildMismatchError,
    ContextResolverService,
    ContextRoleNotFoundError,
    UnsupportedContextValueTypeError,
)


def create_role(
    *,
    role_id: int,
    position: int = 10,
    managed: bool = False,
) -> Mock:
    """Create one Discord role for context resolution tests."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = f"role-{role_id}"
    role.position = position
    role.managed = managed

    role.__lt__ = Mock(
        return_value=True,
    )

    return role


def create_member(
    *,
    guild_id: int = 123,
    available_roles: dict[int, Mock] | None = None,
    member_role_ids: tuple[int, ...] = (),
    bot_available: bool = True,
) -> Mock:
    """Create one Discord member with deterministic guild state."""

    guild = Mock(
        spec=discord.Guild,
    )

    guild.id = guild_id

    roles_by_id = available_roles or {}

    guild.get_role = Mock(side_effect=lambda role_id: roles_by_id.get(role_id))

    if bot_available:
        bot_member = Mock(
            spec=discord.Member,
        )

        bot_top_role = Mock(
            spec=discord.Role,
        )

        bot_top_role.position = 100
        bot_member.top_role = bot_top_role

        guild.me = bot_member

    else:
        guild.me = None

    member = Mock(
        spec=discord.Member,
    )

    member.guild = guild

    member.roles = [
        roles_by_id[role_id] for role_id in member_role_ids if role_id in roles_by_id
    ]

    return member


def create_binding(
    *,
    guild_id: int = 123,
    context_key: str = "ai-content",
    capability_key: str = "ai_preference",
    role_id: int = 111,
    value_type: str = "boolean",
    interaction_mode: str = "editable",
    context_enabled: bool = True,
    binding_enabled: bool = True,
) -> WorkflowContextBinding:
    """Create one declarative workflow context binding."""

    return WorkflowContextBinding(
        context=ContextDefinition(
            guild_id=guild_id,
            context_key=context_key,
            capability_key=capability_key,
            value_type=value_type,  # type: ignore[arg-type]
            role_id=role_id,
            label="Allow AI-generated content?",
            description=None,
            sort_order=0,
            enabled=context_enabled,
        ),
        interaction_mode=interaction_mode,  # type: ignore[arg-type]
        sort_order=0,
        enabled=binding_enabled,
    )


def test_resolve_returns_true_when_member_has_context_role() -> None:
    """Resolve a role-backed boolean context to true."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
        member_role_ids=(111,),
    )

    result = ContextResolverService().resolve(
        create_binding(),
        member,
    )

    assert result.current_value is True
    assert result.context_key == "ai-content"
    assert result.capability_key == "ai_preference"


def test_resolve_returns_false_when_member_lacks_context_role() -> None:
    """Resolve a role-backed boolean context to false."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(),
        member,
    )

    assert result.current_value is False


def test_resolve_reports_editable_manageable_context() -> None:
    """Expose whether an editable context can actually be changed."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(
            interaction_mode="editable",
        ),
        member,
    )

    assert result.active is True
    assert result.editable is True
    assert result.role_manageable is True
    assert result.can_edit is True


def test_resolve_preserves_unmanageable_editable_context() -> None:
    """Observe an invalid editable context without hiding its state."""

    role = create_role(
        role_id=111,
        managed=True,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(
            interaction_mode="editable",
        ),
        member,
    )

    assert result.current_value is False
    assert result.editable is True
    assert result.role_manageable is False
    assert result.can_edit is False


def test_read_only_context_never_becomes_editable() -> None:
    """Keep read-only contexts observable even when their role is manageable."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(
            interaction_mode="read_only",
        ),
        member,
    )

    assert result.active is True
    assert result.editable is False
    assert result.role_manageable is True
    assert result.can_edit is False


def test_disabled_context_is_not_active() -> None:
    """Preserve disabled context state for later workflow filtering."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(
            context_enabled=False,
        ),
        member,
    )

    assert result.active is False
    assert result.editable is False
    assert result.can_edit is False


def test_disabled_binding_is_not_active() -> None:
    """Preserve disabled binding state for later workflow filtering."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    result = ContextResolverService().resolve(
        create_binding(
            binding_enabled=False,
        ),
        member,
    )

    assert result.active is False
    assert result.editable is False
    assert result.can_edit is False


def test_missing_bot_member_makes_role_unmanageable() -> None:
    """Resolve current state even when Claviger's member is unavailable."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
        member_role_ids=(111,),
        bot_available=False,
    )

    result = ContextResolverService().resolve(
        create_binding(),
        member,
    )

    assert result.current_value is True
    assert result.role_manageable is False
    assert result.can_edit is False


def test_resolve_rejects_missing_context_role() -> None:
    """Fail when the role backing a configured context disappeared."""

    member = create_member()

    with pytest.raises(
        ContextRoleNotFoundError,
        match="111",
    ):
        ContextResolverService().resolve(
            create_binding(),
            member,
        )


def test_resolve_rejects_context_from_another_guild() -> None:
    """Never resolve guild configuration against another Discord guild."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        guild_id=456,
        available_roles={
            111: role,
        },
    )

    with pytest.raises(
        ContextGuildMismatchError,
        match="123",
    ):
        ContextResolverService().resolve(
            create_binding(
                guild_id=123,
            ),
            member,
        )


def test_resolve_rejects_unsupported_value_type() -> None:
    """Fail closed when a context uses a value type unknown to the runtime."""

    role = create_role(
        role_id=111,
    )

    member = create_member(
        available_roles={
            111: role,
        },
    )

    with pytest.raises(
        UnsupportedContextValueTypeError,
        match="text",
    ):
        ContextResolverService().resolve(
            create_binding(
                value_type="text",
            ),
            member,
        )


def test_resolve_workflow_preserves_context_order() -> None:
    """Resolve workflow contexts in their declarative order."""

    first_role = create_role(
        role_id=111,
    )

    second_role = create_role(
        role_id=222,
    )

    member = create_member(
        available_roles={
            111: first_role,
            222: second_role,
        },
        member_role_ids=(222,),
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="preferences",
        command_name="preferences",
        command_description="Configure preferences.",
        title="Preferences",
        description=None,
        policy_key="public",
        channel_mode="any",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(),
        contexts=(
            create_binding(
                context_key="ai-content",
                capability_key="ai_preference",
                role_id=111,
            ),
            create_binding(
                context_key="secondary",
                capability_key="secondary_preference",
                role_id=222,
                interaction_mode="read_only",
            ),
        ),
    )

    result = ContextResolverService().resolve_workflow(
        workflow,
        member,
    )

    assert tuple(context.context_key for context in result) == (
        "ai-content",
        "secondary",
    )

    assert tuple(context.current_value for context in result) == (
        False,
        True,
    )


def test_resolve_workflow_rejects_another_guild() -> None:
    """Reject a workflow definition belonging to another guild."""

    member = create_member(
        guild_id=456,
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="preferences",
        command_name="preferences",
        command_description="Configure preferences.",
        title="Preferences",
        description=None,
        policy_key="public",
        channel_mode="any",
        sort_order=0,
        enabled=True,
        channel_ids=(),
        catalogs=(),
        contexts=(),
    )

    with pytest.raises(
        ContextGuildMismatchError,
        match="123",
    ):
        ContextResolverService().resolve_workflow(
            workflow,
            member,
        )
