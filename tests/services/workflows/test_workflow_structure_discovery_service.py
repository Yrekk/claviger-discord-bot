from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.roles.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)
from claviger.services.workflows.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)

pytestmark = pytest.mark.asyncio


def _permissions(
    *,
    view_channel: bool,
    send_messages: bool,
) -> Mock:
    """Create one deterministic effective Discord permission snapshot."""

    permissions = Mock(
        spec=discord.Permissions,
    )
    permissions.view_channel = view_channel
    permissions.send_messages = send_messages

    return permissions


def _overwrite(
    *,
    send_messages: bool | None,
) -> Mock:
    """Create one explicit Discord permission overwrite snapshot."""

    overwrite = Mock(
        spec=discord.PermissionOverwrite,
    )
    overwrite.send_messages = send_messages

    return overwrite


def _category(
    *,
    category_id: int,
    name: str,
    default_role: Mock,
    bot_member: Mock,
    everyone_can_view: bool = True,
    bot_can_view: bool = True,
) -> Mock:
    """Create one Discord category candidate with controlled permissions."""

    category = Mock(
        spec=discord.CategoryChannel,
    )
    category.id = category_id
    category.name = name

    def permissions_for(
        target: object,
    ) -> Mock:
        if target is default_role:
            return _permissions(
                view_channel=everyone_can_view,
                send_messages=True,
            )

        if target is bot_member:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=True,
            )

        raise AssertionError("Unexpected permission target.")

    category.permissions_for.side_effect = permissions_for

    return category


def _text_channel(
    *,
    channel_id: int,
    name: str,
    category_id: int | None,
    default_role: Mock,
    bot_member: Mock,
    application_role: Mock,
    everyone_can_view: bool = True,
    everyone_can_send: bool = True,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
    everyone_send_override: bool | None = None,
    application_role_send_override: bool | None = None,
) -> Mock:
    """Create one Discord text channel with controlled effective and raw state."""

    channel = Mock(
        spec=discord.TextChannel,
    )
    channel.id = channel_id
    channel.name = name
    channel.category_id = category_id

    def permissions_for(
        target: object,
    ) -> Mock:
        if target is default_role:
            return _permissions(
                view_channel=everyone_can_view,
                send_messages=everyone_can_send,
            )

        if target is bot_member:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=bot_can_send,
            )

        raise AssertionError("Unexpected permission target.")

    def overwrites_for(
        target: object,
    ) -> Mock:
        if target is default_role:
            return _overwrite(
                send_messages=everyone_send_override,
            )

        if target is application_role:
            return _overwrite(
                send_messages=application_role_send_override,
            )

        raise AssertionError("Unexpected overwrite target.")

    channel.permissions_for.side_effect = permissions_for
    channel.overwrites_for.side_effect = overwrites_for

    return channel


def _role(
    *,
    role_id: int,
    name: str,
) -> Mock:
    """Create one Discord role."""

    role = Mock(
        spec=discord.Role,
    )
    role.id = role_id
    role.name = name

    return role


def _service(
    *,
    application_role: Mock,
    manageable_roles: list[Mock],
) -> WorkflowStructureDiscoveryService:
    """Create workflow discovery around the authoritative role hierarchy."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )
    role_discovery_service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=application_role,
            trusted_roles=[],
            manageable_roles=manageable_roles,
            unmanageable_roles=[],
        )
    )

    return WorkflowStructureDiscoveryService(
        role_discovery_service=role_discovery_service,
    )


def _guild(
    *,
    default_role: Mock,
    bot_member: Mock,
    channels: list[Mock],
    can_create_channels: bool = True,
    can_create_roles: bool = True,
) -> Mock:
    """Create one guild exposing deterministic workflow resources."""

    bot_member.guild_permissions = Mock(
        spec=discord.Permissions,
    )
    bot_member.guild_permissions.manage_channels = can_create_channels
    bot_member.guild_permissions.manage_roles = can_create_roles

    guild = Mock(
        spec=discord.Guild,
    )
    guild.me = bot_member
    guild.default_role = default_role
    guild.channels = channels

    return guild


async def test_discover_exposes_atomic_resources_and_raw_everyone_marker() -> None:
    """Expose effective observations and explicit structural markers together."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="Arbitrary",
        default_role=default_role,
        bot_member=bot_member,
    )
    protected = _text_channel(
        channel_id=200,
        name="alpha",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        everyone_send_override=False,
        application_role_send_override=True,
    )
    interactive = _text_channel(
        channel_id=201,
        name="zulu",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[interactive, category, protected],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[_role(role_id=300, name="Role")],
    )

    result = await service.discover(guild)

    assert tuple(channel.channel_id for channel in result.text_channels) == (200, 201)

    channels = {channel.channel_id: channel for channel in result.text_channels}
    assert channels[200].everyone_can_send is False
    assert channels[200].everyone_send_override is False
    assert channels[200].application_role_send_override is True
    assert channels[201].everyone_can_send is True
    assert channels[201].everyone_send_override is True

    assert result.manageable_roles[0].role_id == 300
    assert result.can_create_channels is True
    assert result.can_create_roles is True


async def test_discover_uses_explicit_overrides_even_when_visibility_changes_effective_send() -> (
    None
):
    """Ignore visibility-driven effective permissions when recognizing structure."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="Hidden Workflow",
        default_role=default_role,
        bot_member=bot_member,
        everyone_can_view=False,
    )
    protected = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_view=False,
        everyone_can_send=False,
        everyone_send_override=False,
    )
    interactive = _text_channel(
        channel_id=201,
        name="command",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_view=False,
        # Effective send can be false because the channel is not visible.
        everyone_can_send=False,
        # The explicit structural marker remains authoritative.
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, protected, interactive],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert len(result.workflow_candidates) == 1
    candidate = result.workflow_candidates[0]
    assert candidate.protected_channels[0].channel_id == 200
    assert candidate.interactive_channels[0].channel_id == 201


async def test_discover_ignores_application_and_bot_send_state_for_recognition() -> None:
    """Recognize the @everyone pattern independently from application access."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )
    protected = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        bot_can_send=False,
        everyone_send_override=False,
        application_role_send_override=False,
    )
    interactive = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        bot_can_send=False,
        everyone_send_override=True,
        application_role_send_override=None,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, protected, interactive],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert len(result.workflow_candidates) == 1


async def test_discover_requires_explicit_everyone_deny() -> None:
    """Do not treat inherited or merely effective denial as a protected marker."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )
    inherited_deny = _text_channel(
        channel_id=200,
        name="looks-protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        everyone_send_override=None,
    )
    interactive = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, inherited_deny, interactive],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.workflow_candidates == ()


async def test_discover_requires_explicit_everyone_allow() -> None:
    """Do not treat inherited or merely effective allowance as an interactive marker."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )
    protected = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=False,
    )
    inherited_allow = _text_channel(
        channel_id=201,
        name="looks-interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
        everyone_send_override=None,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, protected, inherited_allow],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.workflow_candidates == ()


async def test_discover_preserves_multiple_choices_without_semantic_inference() -> None:
    """Keep every matching channel and leave ambiguous meaning to the human."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="PORTA",
        default_role=default_role,
        bot_member=bot_member,
    )
    protected_a = _text_channel(
        channel_id=200,
        name="vestibulum",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=False,
    )
    interactive_a = _text_channel(
        channel_id=201,
        name="salutationes",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=True,
    )
    protected_b = _text_channel(
        channel_id=202,
        name="index",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=False,
    )
    interactive_b = _text_channel(
        channel_id=203,
        name="requests",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, protected_a, interactive_a, protected_b, interactive_b],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    candidate = result.workflow_candidates[0]
    assert {channel.channel_id for channel in candidate.protected_channels} == {
        200,
        202,
    }
    assert {channel.channel_id for channel in candidate.interactive_channels} == {
        201,
        203,
    }
    assert candidate.requires_protected_channel_choice is True
    assert candidate.requires_interactive_channel_choice is True


async def test_discover_never_combines_markers_from_different_categories() -> None:
    """Require deny and allow markers inside the same Discord category."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category_a = _category(
        category_id=100,
        name="A",
        default_role=default_role,
        bot_member=bot_member,
    )
    category_b = _category(
        category_id=101,
        name="B",
        default_role=default_role,
        bot_member=bot_member,
    )
    protected = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=False,
    )
    interactive = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=101,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category_a, category_b, protected, interactive],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.workflow_candidates == ()


async def test_discover_returns_every_matching_category() -> None:
    """Return multiple valid structures without choosing between them."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category_a = _category(
        category_id=100,
        name="Alpha",
        default_role=default_role,
        bot_member=bot_member,
    )
    category_b = _category(
        category_id=101,
        name="Beta",
        default_role=default_role,
        bot_member=bot_member,
    )

    channels = [
        _text_channel(
            channel_id=200,
            name="alpha-protected",
            category_id=100,
            default_role=default_role,
            bot_member=bot_member,
            application_role=application_role,
            everyone_send_override=False,
        ),
        _text_channel(
            channel_id=201,
            name="alpha-interactive",
            category_id=100,
            default_role=default_role,
            bot_member=bot_member,
            application_role=application_role,
            everyone_send_override=True,
        ),
        _text_channel(
            channel_id=202,
            name="beta-protected",
            category_id=101,
            default_role=default_role,
            bot_member=bot_member,
            application_role=application_role,
            everyone_send_override=False,
        ),
        _text_channel(
            channel_id=203,
            name="beta-interactive",
            category_id=101,
            default_role=default_role,
            bot_member=bot_member,
            application_role=application_role,
            everyone_send_override=True,
        ),
    ]

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category_b, *channels, category_a],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert tuple(
        candidate.category.category_id
        for candidate in result.workflow_candidates
    ) == (100, 101)


async def test_discover_does_not_use_names_to_recognize_structure() -> None:
    """Reject semantic-looking names when explicit markers do not match."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    category = _category(
        category_id=100,
        name="workflow-member",
        default_role=default_role,
        bot_member=bot_member,
    )
    fake_rules = _text_channel(
        channel_id=200,
        name="rules",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=None,
    )
    fake_command = _text_channel(
        channel_id=201,
        name="member-command",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=None,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[category, fake_rules, fake_command],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.workflow_candidates == ()


async def test_discover_reports_creation_capabilities_separately() -> None:
    """Keep creation capabilities independent from structural recognition."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[],
        can_create_channels=False,
        can_create_roles=False,
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.can_create_channels is False
    assert result.can_create_roles is False


async def test_discover_preserves_uncategorized_channel_without_structure() -> None:
    """Expose uncategorized channels but never promote them to workflow candidates."""

    default_role = _role(role_id=1, name="@everyone")
    bot_member = Mock(spec=discord.Member)
    application_role = _role(role_id=10, name="Application")

    channel = _text_channel(
        channel_id=200,
        name="general",
        category_id=None,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[channel],
    )
    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(guild)

    assert result.text_channels[0].category_id is None
    assert result.workflow_candidates == ()


async def test_discover_fails_when_bot_member_is_unavailable() -> None:
    """Fail closed when Discord cannot identify the application inside the guild."""

    application_role = _role(role_id=10, name="Application")
    guild = Mock(spec=discord.Guild)
    guild.me = None

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    with pytest.raises(
        RuntimeError,
        match="own member",
    ):
        await service.discover(guild)
