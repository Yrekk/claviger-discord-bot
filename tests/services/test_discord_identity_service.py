from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from claviger.services.discord_identity_service import (
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
        normalize_application_command_name("!!!")


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
async def test_resolve_discord_runtime_identity() -> None:
    """Resolve application identity and guild-specific bot display name."""

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

    client.fetch_guild.assert_awaited_once_with(
        123,
    )

    guild.fetch_member.assert_awaited_once_with(
        456,
    )


@pytest.mark.asyncio
async def test_resolve_rejects_missing_authenticated_bot() -> None:
    """Fail closed when Discord has not authenticated a bot user."""

    client = Mock(
        spec=discord.Client,
    )

    client.user = None

    with pytest.raises(
        RuntimeError,
        match="Discord bot identity is unavailable",
    ):
        await DiscordIdentityService().resolve(
            client,
            guild_id=123,
        )
