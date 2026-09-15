from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)
from claviger.services.workflow_structure_discovery_service import (
    WorkflowStructureDiscoveryService,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Discord mock builders
# ---------------------------------------------------------------------------


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
    application_role_send_override: bool | None = None,
) -> Mock:
    """Create one Discord text channel with controlled permission state."""

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


# ---------------------------------------------------------------------------
# Atomic resource discovery
# ---------------------------------------------------------------------------


async def test_discover_exposes_existing_workflow_resources() -> None:
    """Expose categories, text channels and safely manageable roles."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Completely Arbitrary Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    protected_channel = _text_channel(
        channel_id=200,
        name="alpha",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        application_role_send_override=True,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="zulu",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            interactive_channel,
            category,
            protected_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[
            _role(
                role_id=300,
                name="Unconfigured Role",
            ),
        ],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.categories) == 1
    assert result.categories[0].category_id == 100
    assert result.categories[0].category_name == "Completely Arbitrary Category"

    assert tuple(channel.channel_id for channel in result.text_channels) == (
        200,
        201,
    )

    channels_by_id = {channel.channel_id: channel for channel in result.text_channels}

    assert channels_by_id[200].everyone_can_send is False
    assert channels_by_id[200].application_role_send_override is True

    assert channels_by_id[201].everyone_can_send is True
    assert channels_by_id[201].application_role_send_override is None

    assert len(result.manageable_roles) == 1
    assert result.manageable_roles[0].role_id == 300
    assert result.manageable_roles[0].role_name == "Unconfigured Role"

    assert result.can_create_channels is True
    assert result.can_create_roles is True


async def test_discover_reports_creation_capabilities_separately() -> None:
    """Keep existing imports available when creation permissions are absent."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    existing_channel = _text_channel(
        channel_id=200,
        name="existing",
        category_id=None,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            existing_channel,
        ],
        can_create_channels=False,
        can_create_roles=False,
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[
            _role(
                role_id=300,
                name="Existing Role",
            ),
        ],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.text_channels) == 1
    assert len(result.manageable_roles) == 1

    assert result.can_create_channels is False
    assert result.can_create_roles is False


async def test_discover_preserves_channel_without_category() -> None:
    """Expose uncategorized channels instead of silently discarding them."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    channel = _text_channel(
        channel_id=200,
        name="general",
        category_id=None,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.text_channels) == 1
    assert result.text_channels[0].category_id is None

    assert result.workflow_candidates == ()


# ---------------------------------------------------------------------------
# Structural workflow recognition
# ---------------------------------------------------------------------------


async def test_discover_recognizes_one_structural_workflow_candidate() -> None:
    """Recognize one category containing one protected and one interactive channel."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Absolutely Not A Semantic Name",
        default_role=default_role,
        bot_member=bot_member,
    )

    protected_channel = _text_channel(
        channel_id=200,
        name="first-random-name",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="second-random-name",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            protected_channel,
            interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.workflow_candidates) == 1

    candidate = result.workflow_candidates[0]

    assert candidate.category.category_id == 100

    assert tuple(channel.channel_id for channel in candidate.protected_channels) == (
        200,
    )

    assert tuple(channel.channel_id for channel in candidate.interactive_channels) == (
        201,
    )

    assert candidate.requires_protected_channel_choice is False
    assert candidate.requires_interactive_channel_choice is False


async def test_discover_recognizes_index_like_protected_channel_without_semantics() -> (
    None
):
    """Keep several protected channels when only one interactive channel exists."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="PORTA",
        default_role=default_role,
        bot_member=bot_member,
    )

    first_protected_channel = _text_channel(
        channel_id=200,
        name="vestibulum",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="salutationes",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    second_protected_channel = _text_channel(
        channel_id=202,
        name="index",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            first_protected_channel,
            interactive_channel,
            second_protected_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.workflow_candidates) == 1

    candidate = result.workflow_candidates[0]

    assert tuple(channel.channel_id for channel in candidate.protected_channels) == (
        202,
        200,
    )

    assert tuple(channel.channel_id for channel in candidate.interactive_channels) == (
        201,
    )

    assert candidate.requires_protected_channel_choice is True
    assert candidate.requires_interactive_channel_choice is False


async def test_discover_keeps_multiple_interactive_channels_for_human_choice() -> None:
    """Expose every interactive option instead of choosing one silently."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    protected_channel = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    first_interactive_channel = _text_channel(
        channel_id=201,
        name="interactive-a",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    second_interactive_channel = _text_channel(
        channel_id=202,
        name="interactive-b",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            protected_channel,
            first_interactive_channel,
            second_interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.workflow_candidates) == 1

    candidate = result.workflow_candidates[0]

    assert tuple(channel.channel_id for channel in candidate.interactive_channels) == (
        201,
        202,
    )

    assert candidate.requires_protected_channel_choice is False
    assert candidate.requires_interactive_channel_choice is True


async def test_discover_requires_explicit_application_role_send_allow() -> None:
    """Do not infer a protected workflow channel from effective bot access alone."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    protected_looking_channel = _text_channel(
        channel_id=200,
        name="protected-looking",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=None,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            protected_looking_channel,
            interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_rejects_explicit_application_role_send_deny() -> None:
    """Do not classify a channel protected when the application role is denied."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    denied_channel = _text_channel(
        channel_id=200,
        name="denied",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=False,
        application_role_send_override=False,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            denied_channel,
            interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_requires_effective_bot_send_access_on_protected_channel() -> (
    None
):
    """Fail structural recognition when the role allow is not effective for the bot."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    inaccessible_protected_channel = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=False,
        application_role_send_override=True,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            inaccessible_protected_channel,
            interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_requires_at_least_one_interactive_channel() -> None:
    """Do not recognize categories containing only protected channels."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="Category",
        default_role=default_role,
        bot_member=bot_member,
    )

    first_protected_channel = _text_channel(
        channel_id=200,
        name="protected-a",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    second_protected_channel = _text_channel(
        channel_id=201,
        name="protected-b",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            first_protected_channel,
            second_protected_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_requires_protected_and_interactive_channels_in_same_category() -> (
    None
):
    """Never combine matching channels belonging to different categories."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    protected_category = _category(
        category_id=100,
        name="First",
        default_role=default_role,
        bot_member=bot_member,
    )

    interactive_category = _category(
        category_id=101,
        name="Second",
        default_role=default_role,
        bot_member=bot_member,
    )

    protected_channel = _text_channel(
        channel_id=200,
        name="protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    interactive_channel = _text_channel(
        channel_id=201,
        name="interactive",
        category_id=101,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            protected_category,
            interactive_category,
            protected_channel,
            interactive_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_exposes_multiple_structural_candidates_without_choosing() -> (
    None
):
    """Return every compatible category and leave selection to the caller."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    first_category = _category(
        category_id=100,
        name="Alpha",
        default_role=default_role,
        bot_member=bot_member,
    )

    second_category = _category(
        category_id=101,
        name="Beta",
        default_role=default_role,
        bot_member=bot_member,
    )

    first_protected = _text_channel(
        channel_id=200,
        name="alpha-protected",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    first_interactive = _text_channel(
        channel_id=201,
        name="alpha-interactive",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    second_protected = _text_channel(
        channel_id=202,
        name="beta-protected",
        category_id=101,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=False,
        bot_can_send=True,
        application_role_send_override=True,
    )

    second_interactive = _text_channel(
        channel_id=203,
        name="beta-interactive",
        category_id=101,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            second_category,
            first_interactive,
            first_category,
            second_protected,
            first_protected,
            second_interactive,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert tuple(
        candidate.category.category_id for candidate in result.workflow_candidates
    ) == (
        100,
        101,
    )


async def test_discover_does_not_use_names_to_recognize_structure() -> None:
    """Reject semantic-looking names when the permission pattern does not match."""

    default_role = _role(
        role_id=1,
        name="@everyone",
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    application_role = _role(
        role_id=10,
        name="Application",
    )

    category = _category(
        category_id=100,
        name="workflow-member",
        default_role=default_role,
        bot_member=bot_member,
    )

    fake_rules_channel = _text_channel(
        channel_id=200,
        name="rules",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    fake_execution_channel = _text_channel(
        channel_id=201,
        name="member-command",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        application_role=application_role,
        everyone_can_send=True,
    )

    guild = _guild(
        default_role=default_role,
        bot_member=bot_member,
        channels=[
            category,
            fake_rules_channel,
            fake_execution_channel,
        ],
    )

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert result.workflow_candidates == ()


async def test_discover_fails_when_bot_member_is_unavailable() -> None:
    """Fail closed when Discord cannot identify the application inside the guild."""

    application_role = _role(
        role_id=10,
        name="Application",
    )

    guild = Mock(
        spec=discord.Guild,
    )

    guild.me = None

    service = _service(
        application_role=application_role,
        manageable_roles=[],
    )

    with pytest.raises(
        RuntimeError,
        match="own member",
    ):
        await service.discover(
            guild,
        )
