from unittest.mock import MagicMock

import discord

from claviger.services.admin_structure_discovery_service import (
    AdminStructureDiscoveryService,
)


def _permissions(
    *,
    view_channel: bool,
) -> discord.Permissions:
    """Create minimal deterministic Discord permissions."""

    permissions = discord.Permissions.none()

    permissions.update(
        view_channel=view_channel,
    )

    return permissions


def test_discover_includes_configured_category_after_rename() -> None:
    """Resolve a persisted ADMIN category by ID even without 'admin' in its name."""

    default_role = MagicMock(
        spec=discord.Role,
    )

    bot_member = MagicMock(
        spec=discord.Member,
    )

    category = MagicMock(
        spec=discord.CategoryChannel,
    )

    category.id = 100
    category.name = "Sanctum Mechanicum"
    category.channels = []

    def category_permissions_for(
        target: discord.Role | discord.Member,
    ) -> discord.Permissions:
        if target is default_role:
            return _permissions(
                view_channel=False,
            )

        return _permissions(
            view_channel=True,
        )

    category.permissions_for.side_effect = category_permissions_for

    guild = MagicMock(
        spec=discord.Guild,
    )

    guild.default_role = default_role
    guild.me = bot_member
    guild.channels = [
        category,
    ]

    result = AdminStructureDiscoveryService().discover(
        guild,
        configured_category_id=100,
    )

    assert result.single_candidate is not None
    assert result.single_candidate.category_id == 100
    assert result.single_candidate.category_name == "Sanctum Mechanicum"
