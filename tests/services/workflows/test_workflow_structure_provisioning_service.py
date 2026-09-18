from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from claviger.models.workflows.workflow_configuration_inspection_model import (
    WorkflowConfigurationInspection,
)
from claviger.models.workflows.workflow_configuration_model import (
    WorkflowConfigurationSpec,
    WorkflowResourceSelection,
)
from claviger.services.roles.role_discovery import (
    RoleDiscoveryService,
    RoleHierarchy,
)
from claviger.services.workflows.workflow_configuration_inspection_service import (
    WorkflowConfigurationInspectionService,
)
from claviger.services.workflows.workflow_structure_provisioning_service import (
    WorkflowStructureProvisioningPartialError,
    WorkflowStructureProvisioningResourceError,
    WorkflowStructureProvisioningService,
)

pytestmark = pytest.mark.asyncio

DEFAULT_ROLE_ID = 1
BOT_MEMBER_ID = 2


# ---------------------------------------------------------------------------
# Discord mock builders
# ---------------------------------------------------------------------------


def _permissions(
    *,
    view_channel: bool = True,
    send_messages: bool = True,
    manage_channels: bool = False,
    manage_roles: bool = False,
) -> discord.Permissions:
    """Create one deterministic Discord permission snapshot."""

    permissions = discord.Permissions.none()

    permissions.update(
        view_channel=view_channel,
        send_messages=send_messages,
        manage_channels=manage_channels,
        manage_roles=manage_roles,
    )

    return permissions


def _role(
    role_id: int,
    name: str,
) -> MagicMock:
    """Create one deterministic Discord role mock."""

    role = MagicMock(
        spec=discord.Role,
    )

    role.id = role_id
    role.name = name

    return role


def _category(
    *,
    category_id: int,
    bot_member: MagicMock,
    bot_can_view: bool = True,
) -> MagicMock:
    """Create one workflow category mock."""

    category = MagicMock(
        spec=discord.CategoryChannel,
    )

    category.id = category_id
    category.name = "Membres"

    def permissions_for(
        target: object,
    ) -> discord.Permissions:
        if target is bot_member:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=True,
            )

        return _permissions()

    category.permissions_for.side_effect = permissions_for
    category.overwrites_for.return_value = discord.PermissionOverwrite()
    category.set_permissions = AsyncMock()

    return category


def _text_channel(
    *,
    channel_id: int,
    category_id: int,
    default_role: MagicMock,
    bot_member: MagicMock,
    everyone_can_send: bool = True,
    bot_can_view: bool = True,
    bot_can_send: bool = True,
) -> MagicMock:
    """Create one workflow text-channel mock."""

    channel = MagicMock(
        spec=discord.TextChannel,
    )

    channel.id = channel_id
    channel.name = f"channel-{channel_id}"
    channel.category_id = category_id

    def permissions_for(
        target: object,
    ) -> discord.Permissions:
        if target is default_role:
            return _permissions(
                view_channel=True,
                send_messages=everyone_can_send,
            )

        if target is bot_member:
            return _permissions(
                view_channel=bot_can_view,
                send_messages=bot_can_send,
            )

        return _permissions()

    channel.permissions_for.side_effect = permissions_for
    channel.overwrites_for.return_value = discord.PermissionOverwrite()
    channel.set_permissions = AsyncMock()

    return channel


def _guild(
    *,
    channels: list[MagicMock] | None = None,
    manage_channels: bool = True,
    manage_roles: bool = True,
) -> MagicMock:
    """Create one Discord guild ready for workflow provisioning."""

    guild = MagicMock(
        spec=discord.Guild,
    )

    guild.id = 123

    default_role = _role(
        DEFAULT_ROLE_ID,
        "@everyone",
    )

    bot_member = MagicMock(
        spec=discord.Member,
    )

    bot_member.id = BOT_MEMBER_ID
    bot_member.guild_permissions = _permissions(
        manage_channels=manage_channels,
        manage_roles=manage_roles,
    )

    guild.default_role = default_role
    guild.me = bot_member
    guild.channels = channels or []

    guild.create_category = AsyncMock()
    guild.create_text_channel = AsyncMock()
    guild.create_role = AsyncMock()

    return guild


def _existing(
    resource_id: int,
) -> WorkflowResourceSelection:
    """Create one existing-resource selection."""

    return WorkflowResourceSelection(
        mode="existing",
        resource_id=resource_id,
    )


def _create(
    name: str,
) -> WorkflowResourceSelection:
    """Create one resource-creation selection."""

    return WorkflowResourceSelection(
        mode="create",
        name=name,
    )


def _configuration(
    *,
    category: WorkflowResourceSelection,
    management_channel: WorkflowResourceSelection,
    execution_channel: WorkflowResourceSelection,
    primary_role: WorkflowResourceSelection,
) -> WorkflowConfigurationSpec:
    """Create one reconciled workflow specification."""

    return WorkflowConfigurationSpec(
        guild_id=123,
        workflow_key="member",
        title="Membre",
        description=None,
        command_name="membre",
        command_description="Gère ton profil membre.",
        category=category,
        management_channel=management_channel,
        execution_channel=execution_channel,
        primary_role=primary_role,
        questionnaire_role_prefix="interest-",
    )


def _service(
    *,
    manageable_roles: list[MagicMock] | None = None,
    inspection: WorkflowConfigurationInspection | None = None,
) -> WorkflowStructureProvisioningService:
    """Create provisioning around the shared authoritative role hierarchy."""

    role_discovery_service = MagicMock(
        spec=RoleDiscoveryService,
    )

    role_discovery_service.get_hierarchy = AsyncMock(
        return_value=RoleHierarchy(
            bot_role=_role(
                999,
                "Claviger",
            ),
            trusted_roles=[],
            manageable_roles=manageable_roles or [],
            unmanageable_roles=[],
        )
    )

    inspection_service = MagicMock(
        spec=WorkflowConfigurationInspectionService,
    )
    inspection_service.inspect = AsyncMock(
        return_value=inspection
        or WorkflowConfigurationInspection(
            guild_id=123,
            workflows=(),
            ai_role_id=None,
            reserved_role_ids=frozenset(),
            reserved_role_prefixes=(),
        )
    )
    inspection_service.is_role_reserved.side_effect = (
        WorkflowConfigurationInspectionService.is_role_reserved
    )

    return WorkflowStructureProvisioningService(
        role_discovery_service=role_discovery_service,
        inspection_service=inspection_service,
    )


# ---------------------------------------------------------------------------
# Full creation
# ---------------------------------------------------------------------------


async def test_provision_creates_complete_workflow_structure() -> None:
    """Create category, channels and roles from one reconciled specification."""

    guild = _guild()

    created_category = _category(
        category_id=100,
        bot_member=guild.me,
    )

    created_management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=False,
    )

    created_execution_channel = _text_channel(
        channel_id=201,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
    )

    created_primary_role = _role(
        300,
        "Membre",
    )
    guild.create_category.return_value = created_category

    guild.create_text_channel.side_effect = [
        created_management_channel,
        created_execution_channel,
    ]

    guild.create_role.side_effect = [
        created_primary_role,
    ]

    service = _service()

    result = await service.provision(
        guild=guild,
        configuration=_configuration(
            category=_create(
                "Membres",
            ),
            management_channel=_create(
                "workflow-info",
            ),
            execution_channel=_create(
                "salutations",
            ),
            primary_role=_create(
                "Membre",
            ),
        ),
    )

    assert result.configuration.category_id == 100
    assert result.configuration.management_channel_id == 200
    assert result.configuration.execution_channel_id == 201
    assert result.configuration.primary_role_id == 300

    assert result.created_category_id == 100
    assert result.created_channel_ids == (
        200,
        201,
    )
    assert result.created_role_ids == (
        300,
    )

    management_call = guild.create_text_channel.await_args_list[0]

    management_overwrites = management_call.kwargs["overwrites"]

    assert management_overwrites[guild.default_role].send_messages is False

    execution_call = guild.create_text_channel.await_args_list[1]

    execution_overwrites = execution_call.kwargs["overwrites"]

    # Execution-channel member behavior continues to inherit from its category.
    assert guild.default_role not in execution_overwrites


# ---------------------------------------------------------------------------
# Existing-resource repair
# ---------------------------------------------------------------------------


async def test_provision_repairs_existing_workflow_permissions() -> None:
    """Repair only permissions required by the configured workflow semantics."""

    guild = _guild()

    category = _category(
        category_id=100,
        bot_member=guild.me,
        bot_can_view=False,
    )

    management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=True,
        bot_can_send=False,
    )

    execution_channel = _text_channel(
        channel_id=201,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        bot_can_view=False,
        bot_can_send=False,
    )

    guild.channels = [
        category,
        management_channel,
        execution_channel,
    ]

    primary_role = _role(
        300,
        "Membre",
    )

    service = _service(
        manageable_roles=[
            primary_role,
        ],
    )

    result = await service.provision(
        guild=guild,
        configuration=_configuration(
            category=_existing(
                100,
            ),
            management_channel=_existing(
                200,
            ),
            execution_channel=_existing(
                201,
            ),
            primary_role=_existing(
                300,
            ),
        ),
    )

    assert result.created_category_id is None
    assert result.created_channel_ids == ()
    assert result.created_role_ids == ()

    assert result.category_permissions_repaired is True

    assert result.repaired_channel_ids == (
        200,
        201,
    )

    category.set_permissions.assert_awaited_once()

    # Management repair denies ordinary writes and restores bot access.
    assert management_channel.set_permissions.await_count == 2

    # Execution repair changes only bot access.
    execution_channel.set_permissions.assert_awaited_once()


# ---------------------------------------------------------------------------
# Fresh preflight safety
# ---------------------------------------------------------------------------


async def test_provision_rejects_role_that_became_unmanageable() -> None:
    """Fail before Discord mutation when role hierarchy changed after reconciliation."""

    guild = _guild()

    category = _category(
        category_id=100,
        bot_member=guild.me,
    )

    management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=False,
    )

    execution_channel = _text_channel(
        channel_id=201,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
    )

    guild.channels = [
        category,
        management_channel,
        execution_channel,
    ]

    service = _service(
        manageable_roles=[],
    )

    with pytest.raises(
        WorkflowStructureProvisioningResourceError,
        match="no longer manageable",
    ):
        await service.provision(
            guild=guild,
            configuration=_configuration(
                category=_existing(
                    100,
                ),
                management_channel=_existing(
                    200,
                ),
                execution_channel=_existing(
                    201,
                ),
                primary_role=_existing(
                    300,
                ),
            ),
        )

    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    guild.create_role.assert_not_awaited()


async def test_provision_rejects_role_reserved_after_reconciliation() -> None:
    """Recheck persisted role reservations immediately before Discord mutation."""

    guild = _guild()

    category = _category(
        category_id=100,
        bot_member=guild.me,
    )
    management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=False,
    )
    execution_channel = _text_channel(
        channel_id=201,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
    )

    guild.channels = [
        category,
        management_channel,
        execution_channel,
    ]

    primary_role = _role(
        300,
        "Membre",
    )
    service = _service(
        manageable_roles=[
            primary_role,
        ],
        inspection=WorkflowConfigurationInspection(
            guild_id=123,
            workflows=(),
            ai_role_id=300,
            reserved_role_ids=frozenset(
                {
                    300,
                }
            ),
            reserved_role_prefixes=(),
        ),
    )

    with pytest.raises(
        WorkflowStructureProvisioningResourceError,
        match="now reserved",
    ):
        await service.provision(
            guild=guild,
            configuration=_configuration(
                category=_existing(
                    100,
                ),
                management_channel=_existing(
                    200,
                ),
                execution_channel=_existing(
                    201,
                ),
                primary_role=_existing(
                    300,
                ),
            ),
        )

    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    guild.create_role.assert_not_awaited()


async def test_provision_rejects_created_primary_role_using_reserved_prefix() -> None:
    """Prevent a new primary role from entering a bound questionnaire namespace."""

    guild = _guild()

    category = _category(
        category_id=100,
        bot_member=guild.me,
    )
    management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=False,
    )
    execution_channel = _text_channel(
        channel_id=201,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
    )

    guild.channels = [
        category,
        management_channel,
        execution_channel,
    ]

    service = _service(
        inspection=WorkflowConfigurationInspection(
            guild_id=123,
            workflows=(),
            ai_role_id=None,
            reserved_role_ids=frozenset(),
            reserved_role_prefixes=(
                "interest-",
            ),
        ),
    )

    with pytest.raises(
        WorkflowStructureProvisioningResourceError,
        match="name is reserved",
    ):
        await service.provision(
            guild=guild,
            configuration=_configuration(
                category=_existing(
                    100,
                ),
                management_channel=_existing(
                    200,
                ),
                execution_channel=_existing(
                    201,
                ),
                primary_role=_create(
                    "interest-admin",
                ),
            ),
        )

    guild.create_category.assert_not_awaited()
    guild.create_text_channel.assert_not_awaited()
    guild.create_role.assert_not_awaited()


# ---------------------------------------------------------------------------
# Partial mutation diagnostics
# ---------------------------------------------------------------------------


async def test_provision_reports_created_resources_before_later_failure() -> None:
    """Expose irreversible Discord mutations when provisioning stops halfway."""

    guild = _guild()

    created_category = _category(
        category_id=100,
        bot_member=guild.me,
    )

    created_management_channel = _text_channel(
        channel_id=200,
        category_id=100,
        default_role=guild.default_role,
        bot_member=guild.me,
        everyone_can_send=False,
    )

    guild.create_category.return_value = created_category

    guild.create_text_channel.side_effect = [
        created_management_channel,
        RuntimeError(
            "Discord execution-channel failure.",
        ),
    ]

    service = _service()

    with pytest.raises(
        WorkflowStructureProvisioningPartialError,
    ) as captured:
        await service.provision(
            guild=guild,
            configuration=_configuration(
                category=_create(
                    "Membres",
                ),
                management_channel=_create(
                    "workflow-info",
                ),
                execution_channel=_create(
                    "salutations",
                ),
                primary_role=_create(
                    "Membre",
                ),
            ),
        )

    error = captured.value

    assert error.created_category_id == 100
    assert error.created_channel_ids == (200,)
    assert error.created_role_ids == ()
