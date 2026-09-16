from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.runtime.discord_identity_service import (
    DiscordIdentityService,
    InvalidApplicationCommandNameError,
    normalize_application_command_name,
)


def test_normalize_application_command_name() -> None:
    """Normalize application names for Discord administrative commands."""

    assert normalize_application_command_name("Claviger") == "claviger"
    assert normalize_application_command_name("Experimentum Bot") == "experimentum-bot"
    assert normalize_application_command_name("Écho   Bot") == "echo-bot"


def test_normalize_application_command_name_rejects_empty_result() -> None:
    """Reject application names that cannot produce a command name."""

    with pytest.raises(
        InvalidApplicationCommandNameError,
        match="cannot produce a valid command name",
    ):
        normalize_application_command_name(
            "!!!",
        )


def test_normalize_application_command_name_rejects_long_result() -> None:
    """Reject command names longer than Discord's supported limit."""

    with pytest.raises(
        InvalidApplicationCommandNameError,
        match="longer than 32 characters",
    ):
        normalize_application_command_name(
            "application-name-that-is-definitely-too-long"
        )


@pytest.mark.asyncio
async def test_resolve_application_identity_without_guild_context() -> None:
    """Resolve application identity without depending on any guild."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = SimpleNamespace(
        id=456,
    )

    client.application_info = AsyncMock(
        return_value=SimpleNamespace(
            id=789,
            name="Experimentum",
        )
    )

    client.fetch_guild = AsyncMock()

    identity = await DiscordIdentityService().resolve_application(
        client,
    )

    assert identity.application_id == 789
    assert identity.application_name == "Experimentum"
    assert identity.bot_user_id == 456
    assert identity.admin_command_name == "experimentum"

    client.application_info.assert_awaited_once()
    client.fetch_guild.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_guild_identity_without_application_lookup() -> None:
    """Resolve only identity values that can vary between guilds."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = SimpleNamespace(
        id=456,
    )

    client.application_info = AsyncMock()

    bot_member = SimpleNamespace(
        display_name="Experimentum DEV",
    )

    guild = Mock()
    guild.fetch_member = AsyncMock(
        return_value=bot_member,
    )

    client.fetch_guild = AsyncMock(
        return_value=guild,
    )

    identity = await DiscordIdentityService().resolve_guild(
        client,
        guild_id=123,
    )

    assert identity.guild_id == 123
    assert identity.bot_display_name == "Experimentum DEV"

    client.application_info.assert_not_awaited()

    client.fetch_guild.assert_awaited_once_with(
        123,
    )

    guild.fetch_member.assert_awaited_once_with(
        456,
    )


@pytest.mark.asyncio
async def test_legacy_resolve_composes_application_and_guild_identity() -> None:
    """Keep the single-guild runtime working during the identity migration."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = SimpleNamespace(
        id=456,
    )

    client.application_info = AsyncMock(
        return_value=SimpleNamespace(
            id=789,
            name="Claviger",
        )
    )

    bot_member = SimpleNamespace(
        display_name="Vespera",
    )

    guild = Mock()
    guild.fetch_member = AsyncMock(
        return_value=bot_member,
    )

    client.fetch_guild = AsyncMock(
        return_value=guild,
    )

    identity = await DiscordIdentityService().resolve(
        client,
        guild_id=123,
    )

    assert identity.application_id == 789
    assert identity.application_name == "Claviger"
    assert identity.bot_user_id == 456
    assert identity.guild_id == 123
    assert identity.bot_display_name == "Vespera"
    assert identity.admin_command_name == "claviger"


@pytest.mark.asyncio
async def test_resolve_application_rejects_missing_authenticated_bot() -> None:
    """Fail closed when application identity has no authenticated bot."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = None

    with pytest.raises(
        RuntimeError,
        match="Discord bot identity is unavailable",
    ):
        await DiscordIdentityService().resolve_application(
            client,
        )


@pytest.mark.asyncio
async def test_resolve_guild_rejects_missing_authenticated_bot() -> None:
    """Fail closed when guild identity has no authenticated bot."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = None

    with pytest.raises(
        RuntimeError,
        match="Discord bot identity is unavailable",
    ):
        await DiscordIdentityService().resolve_guild(
            client,
            guild_id=123,
        )
