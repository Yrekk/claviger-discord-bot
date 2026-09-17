from unittest.mock import AsyncMock, Mock, patch

import discord
import pytest

from claviger.services.runtime.guild_ai_role_provisioning_service import (
    GuildAIRoleProvisioningPartialError,
    GuildAIRoleProvisioningPermissionError,
    GuildAIRoleProvisioningService,
    PROVISIONING_REASON,
)


def _guild(
    *,
    can_manage_roles: bool = True,
) -> Mock:
    """Create one guild with deterministic role-management capability."""

    guild = Mock(spec=discord.Guild)
    bot_member = Mock(spec=discord.Member)
    permissions = Mock(spec=discord.Permissions)
    permissions.manage_roles = can_manage_roles
    bot_member.guild_permissions = permissions
    guild.me = bot_member
    guild.create_role = AsyncMock()
    return guild


def _role(
    *,
    role_id: int = 456,
    name: str = "Accès IA",
) -> Mock:
    """Create one deterministic role returned by Discord provisioning."""

    role = Mock(spec=discord.Role)
    role.id = role_id
    role.name = name
    role.is_default.return_value = False
    return role


@pytest.mark.asyncio
async def test_create_role_normalizes_name_and_uses_explicit_reason() -> None:
    """Create one manageable AI role without leaking UI concerns into provisioning."""

    service = GuildAIRoleProvisioningService()
    guild = _guild()
    role = _role()
    guild.create_role.return_value = role

    with patch(
        "claviger.services.runtime.guild_ai_role_provisioning_service.is_role_manageable",
        return_value=True,
    ):
        result = await service.create_role(
            guild,
            "  Accès IA  ",
        )

    assert result is role
    guild.create_role.assert_awaited_once_with(
        name="Accès IA",
        reason=PROVISIONING_REASON,
    )


@pytest.mark.asyncio
async def test_create_role_rejects_missing_bot_member_before_mutation() -> None:
    """Fail closed when Discord cannot expose Claviger's guild member state."""

    service = GuildAIRoleProvisioningService()
    guild = _guild()
    guild.me = None

    with pytest.raises(GuildAIRoleProvisioningPermissionError):
        await service.create_role(
            guild,
            "Accès IA",
        )

    guild.create_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_role_rejects_missing_manage_roles_permission() -> None:
    """Never request Discord role creation when preflight permissions are absent."""

    service = GuildAIRoleProvisioningService()
    guild = _guild(can_manage_roles=False)

    with pytest.raises(GuildAIRoleProvisioningPermissionError):
        await service.create_role(
            guild,
            "Accès IA",
        )

    guild.create_role.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_role_reports_partial_mutation_when_new_role_is_unmanageable() -> None:
    """Expose the created role ID if post-creation hierarchy validation fails."""

    service = GuildAIRoleProvisioningService()
    guild = _guild()
    role = _role(role_id=999)
    guild.create_role.return_value = role

    with (
        patch(
            "claviger.services.runtime.guild_ai_role_provisioning_service.is_role_manageable",
            return_value=False,
        ),
        pytest.raises(GuildAIRoleProvisioningPartialError) as exc_info,
    ):
        await service.create_role(
            guild,
            "Accès IA",
        )

    assert exc_info.value.role_id == 999


@pytest.mark.asyncio
async def test_create_role_rejects_blank_name_before_mutation() -> None:
    """Keep invalid human input away from Discord provisioning."""

    service = GuildAIRoleProvisioningService()
    guild = _guild()

    with pytest.raises(ValueError):
        await service.create_role(
            guild,
            "   ",
        )

    guild.create_role.assert_not_awaited()
