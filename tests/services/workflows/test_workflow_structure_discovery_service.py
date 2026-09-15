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
    everyone_can_view: bool = True,
    everyone_can_send: bool = True,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> Mock:
    """Create one Discord text channel candidate with controlled permissions."""

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

    channel.permissions_for.side_effect = permissions_for

    return channel


def _role(
    *,
    role_id: int,
    name: str,
) -> Mock:
    """Create one manageable role returned by the shared hierarchy service."""

    role = Mock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name

    return role


def _service(
    *,
    manageable_roles: list[Mock],
) -> WorkflowStructureDiscoveryService:
    """Create workflow discovery around the authoritative role hierarchy."""

    role_discovery_service = Mock(
        spec=RoleDiscoveryService,
    )

    role_discovery_service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=Mock(
                spec=discord.Role,
            ),
            trusted_roles=[],
            manageable_roles=manageable_roles,
            unmanageable_roles=[],
        )
    )

    return WorkflowStructureDiscoveryService(
        role_discovery_service=role_discovery_service,
    )


# ---------------------------------------------------------------------------
# Discovery behavior
# ---------------------------------------------------------------------------


async def test_discover_exposes_existing_workflow_resources() -> None:
    """Expose categories, text channels and safely manageable roles."""

    default_role = Mock(
        spec=discord.Role,
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    bot_member.guild_permissions = Mock(
        spec=discord.Permissions,
    )
    bot_member.guild_permissions.manage_channels = True
    bot_member.guild_permissions.manage_roles = True

    category = _category(
        category_id=100,
        name="Communauté",
        default_role=default_role,
        bot_member=bot_member,
    )

    management_channel = _text_channel(
        channel_id=200,
        name="workflow-info",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
        everyone_can_send=False,
    )

    execution_channel = _text_channel(
        channel_id=201,
        name="salutations",
        category_id=100,
        default_role=default_role,
        bot_member=bot_member,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    guild.me = bot_member
    guild.default_role = default_role
    guild.channels = [
        execution_channel,
        category,
        management_channel,
    ]

    service = _service(
        manageable_roles=[
            _role(
                role_id=300,
                name="Membre",
            ),
        ],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.categories) == 1
    assert result.categories[0].category_id == 100
    assert result.categories[0].category_name == "Communauté"

    assert tuple(channel.channel_id for channel in result.text_channels) == (
        201,
        200,
    )

    channels_by_id = {channel.channel_id: channel for channel in result.text_channels}

    assert channels_by_id[200].everyone_can_send is False
    assert channels_by_id[201].everyone_can_send is True

    assert len(result.manageable_roles) == 1
    assert result.manageable_roles[0].role_id == 300
    assert result.manageable_roles[0].role_name == "Membre"

    assert result.can_create_channels is True
    assert result.can_create_roles is True


async def test_discover_reports_creation_capabilities_separately() -> None:
    """Keep existing imports available when creation permissions are absent."""

    default_role = Mock(
        spec=discord.Role,
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    bot_member.guild_permissions = Mock(
        spec=discord.Permissions,
    )
    bot_member.guild_permissions.manage_channels = False
    bot_member.guild_permissions.manage_roles = False

    existing_channel = _text_channel(
        channel_id=200,
        name="existing",
        category_id=None,
        default_role=default_role,
        bot_member=bot_member,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    guild.me = bot_member
    guild.default_role = default_role
    guild.channels = [
        existing_channel,
    ]

    service = _service(
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

    # Discovery remains observational: existing resources are still exposed.
    assert len(result.text_channels) == 1
    assert len(result.manageable_roles) == 1

    # Frontends can independently disable creation choices.
    assert result.can_create_channels is False
    assert result.can_create_roles is False


async def test_discover_preserves_channel_without_category() -> None:
    """Expose uncategorized channels instead of silently discarding them."""

    default_role = Mock(
        spec=discord.Role,
    )

    bot_member = Mock(
        spec=discord.Member,
    )

    bot_member.guild_permissions = Mock(
        spec=discord.Permissions,
    )
    bot_member.guild_permissions.manage_channels = True
    bot_member.guild_permissions.manage_roles = True

    channel = _text_channel(
        channel_id=200,
        name="general",
        category_id=None,
        default_role=default_role,
        bot_member=bot_member,
    )

    guild = Mock(
        spec=discord.Guild,
    )

    guild.me = bot_member
    guild.default_role = default_role
    guild.channels = [
        channel,
    ]

    service = _service(
        manageable_roles=[],
    )

    result = await service.discover(
        guild,
    )

    assert len(result.text_channels) == 1
    assert result.text_channels[0].category_id is None


async def test_discover_fails_when_bot_member_is_unavailable() -> None:
    """Fail closed when Discord cannot identify Claviger inside the guild."""

    guild = Mock(
        spec=discord.Guild,
    )

    guild.me = None

    service = _service(
        manageable_roles=[],
    )

    with pytest.raises(
        RuntimeError,
        match="own member",
    ):
        await service.discover(
            guild,
        )
