from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from claviger import bot as bot_module
from claviger.bot import ClavigerBot
from claviger.models.discord_runtime_identity_model import (
    DiscordRuntimeIdentity,
)


def _patch_bot_configuration(
    monkeypatch,
    tmp_path,
    *,
    bot_user_id: int = 456,
) -> None:
    """Provide deterministic configuration for bot composition tests."""

    monkeypatch.setattr(
        bot_module,
        "get_discord_guild_id",
        lambda: 123,
    )

    monkeypatch.setattr(
        bot_module,
        "get_discord_bot_user_id",
        lambda: bot_user_id,
    )

    monkeypatch.setattr(
        bot_module,
        "get_database_path",
        lambda: tmp_path / "claviger.db",
    )

    monkeypatch.setattr(
        bot_module,
        "get_error_report_forum_id",
        lambda: None,
    )


def test_claviger_bot_composition(monkeypatch, tmp_path) -> None:
    """Build the complete bot composition without starting Discord."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    assert bot.guild_id == 123
    assert bot.expected_bot_user_id == 456

    assert bot.discord_identity_service is not None
    assert bot.runtime_identity is None

    assert bot.role_manager is not None
    assert bot.role_discovery_service is not None
    assert bot.authorization_service is not None
    assert bot.say_service is not None
    assert bot.role_classifier is not None
    assert bot.adult_access_classifier is not None

    assert bot.database is not None
    assert bot.database_schema is not None
    assert bot.database_status_service is not None

    assert bot.guild_policy_repository is not None
    assert bot.policy_resolver is not None
    assert bot.guild_policy_bootstrap_service is not None

    assert bot.report_service is not None

    assert bot.interest_catalog_repository is not None
    assert bot.access_catalog_repository is not None

    assert bot.catalog_registry is not None
    assert bot.role_channel_discovery_service is not None
    assert bot.catalog_sync_planner is not None
    assert bot.catalog_sync_coordinator_service is not None
    assert bot.catalog_next_coordinator_service is not None

    assert bot.member_interest_questionnaire_service is not None
    assert bot.member_role_planner_service is not None
    assert bot.member_role_executor_service is not None
    assert bot.member_workflow_coordinator_service is not None

    assert bot.adult_access_workflow_service is not None
    assert bot.adult_access_workflow_service.classifier is bot.adult_access_classifier
    assert bot.adult_access_questionnaire_service is not None
    assert bot.noctis_role_planner_service is not None
    assert bot.noctis_role_executor_service is not None
    assert bot.noctis_workflow_coordinator_service is not None

    commands = bot.tree.get_commands(
        guild=bot_module.discord.Object(id=123),
    )

    assert commands == []


@pytest.mark.asyncio
async def test_setup_hook_resolves_identity_registers_commands_and_syncs(
    monkeypatch,
    tmp_path,
) -> None:
    """Resolve runtime identity before registering and synchronizing commands."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    identity = DiscordRuntimeIdentity(
        application_id=789,
        application_name="Experimentum",
        bot_user_id=456,
        guild_id=123,
        bot_display_name="Vespera DEV",
        admin_command_name="experimentum",
    )

    resolve = AsyncMock(
        return_value=identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    sync = AsyncMock(
        return_value=[],
    )

    monkeypatch.setattr(
        bot.tree,
        "sync",
        sync,
    )

    await bot.setup_hook()

    resolve.assert_awaited_once_with(
        bot,
        123,
    )

    assert bot.runtime_identity == identity

    commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(id=123),
        )
    }

    assert set(commands) == {
        "say",
        "membre",
        "noctis",
        "experimentum",
    }

    assert "claviger" not in commands

    assert commands["say"].description == (
        "Fait envoyer un message par Vespera DEV dans le salon actuel."
    )

    assert commands["experimentum"].description == (
        "Commandes d'administration de Experimentum."
    )

    sync.assert_awaited_once()

    guild = sync.await_args.kwargs["guild"]

    assert guild.id == 123


@pytest.mark.asyncio
async def test_setup_hook_rejects_unexpected_bot_identity_before_sync(
    monkeypatch,
    tmp_path,
) -> None:
    """Never synchronize commands when the token belongs to another bot."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=999,
    )

    resolve = AsyncMock()

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    sync = AsyncMock(
        return_value=[],
    )

    monkeypatch.setattr(
        bot.tree,
        "sync",
        sync,
    )

    with pytest.raises(
        RuntimeError,
        match="Authenticated Discord bot identity does not match configuration",
    ):
        await bot.setup_hook()

    resolve.assert_not_awaited()
    sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_hook_rejects_missing_authenticated_identity(
    monkeypatch,
    tmp_path,
) -> None:
    """Fail closed when Discord identity is unavailable during startup."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = None

    resolve = AsyncMock()

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    sync = AsyncMock(
        return_value=[],
    )

    monkeypatch.setattr(
        bot.tree,
        "sync",
        sync,
    )

    with pytest.raises(
        RuntimeError,
        match="Discord bot identity is unavailable",
    ):
        await bot.setup_hook()

    resolve.assert_not_awaited()
    sync.assert_not_awaited()
