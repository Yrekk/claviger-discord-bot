from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from claviger import bot as bot_module
from claviger.bot import ClavigerBot
from claviger.commands.admin.restart_command import create_restart_command

pytestmark = pytest.mark.asyncio


def _bot(monkeypatch, tmp_path) -> ClavigerBot:
    """Build one deterministic runtime for restart lifecycle tests."""

    monkeypatch.setattr(bot_module, "get_discord_guild_id", lambda: 123)
    monkeypatch.setattr(bot_module, "get_discord_bot_user_id", lambda: 456)
    monkeypatch.setattr(
        bot_module,
        "get_database_path",
        lambda: tmp_path / "claviger.db",
    )
    bot = ClavigerBot()
    bot.tree._command_observability_service = SimpleNamespace(
        record_completion=AsyncMock(),
    )
    return bot


def _interaction(
    bot: ClavigerBot,
    *,
    token: str,
) -> SimpleNamespace:
    """Create the minimal Discord interaction needed by the restart command."""

    return SimpleNamespace(
        guild=SimpleNamespace(owner_id=42),
        user=SimpleNamespace(id=42),
        response=SimpleNamespace(send_message=AsyncMock()),
        application_id=789,
        token=token,
        client=bot,
    )


async def test_restart_waits_for_command_completion_before_closing(
    monkeypatch,
    tmp_path,
) -> None:
    """Never dismantle discord.py while its restart callback is still unwinding."""

    bot = _bot(monkeypatch, tmp_path)
    close = AsyncMock()
    monkeypatch.setattr(bot, "close", close)

    command = create_restart_command(bot.request_restart)
    interaction = _interaction(bot, token="restart-token")

    await command.callback(interaction)

    interaction.response.send_message.assert_awaited_once()
    close.assert_not_awaited()
    assert bot.restart_requested is False
    assert bot.pending_restart_request is None

    await bot.on_app_command_completion(interaction, command)

    close.assert_awaited_once_with()
    assert bot.restart_requested is True
    assert bot.pending_restart_request is not None
    assert bot.pending_restart_request.interaction_token == "restart-token"


async def test_unrelated_completion_cannot_trigger_scheduled_restart(
    monkeypatch,
    tmp_path,
) -> None:
    """Only the completion event for the restart interaction may close the client."""

    bot = _bot(monkeypatch, tmp_path)
    close = AsyncMock()
    monkeypatch.setattr(bot, "close", close)

    command = create_restart_command(bot.request_restart)
    restart_interaction = _interaction(bot, token="restart-token")
    other_interaction = _interaction(bot, token="another-command-token")

    await command.callback(restart_interaction)

    await bot.on_app_command_completion(
        other_interaction,
        SimpleNamespace(),
    )

    close.assert_not_awaited()
    assert bot.restart_requested is False

    await bot.on_app_command_completion(
        restart_interaction,
        command,
    )

    close.assert_awaited_once_with()
    assert bot.restart_requested is True
