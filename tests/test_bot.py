from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from claviger import bot as bot_module
from claviger.bot import ClavigerBot
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)
from claviger.models.discord_runtime_identity_model import (
    DiscordRuntimeIdentity,
)
from claviger.models.runtime_restart_model import RuntimeRestartRequest
from claviger.services.database_ownership_service import (
    DatabaseOwnershipMismatchError,
    DatabaseOwnershipUnboundError,
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


def _create_runtime_identity(
    *,
    application_id: int = 789,
    application_name: str = "Experimentum",
    bot_user_id: int = 456,
    guild_id: int = 123,
    bot_display_name: str = "Vespera DEV",
    admin_command_name: str = "experimentum",
) -> DiscordRuntimeIdentity:
    """Create a deterministic Discord runtime identity."""

    return DiscordRuntimeIdentity(
        application_id=application_id,
        application_name=application_name,
        bot_user_id=bot_user_id,
        guild_id=guild_id,
        bot_display_name=bot_display_name,
        admin_command_name=admin_command_name,
    )


def test_claviger_bot_composition(
    monkeypatch,
    tmp_path,
) -> None:
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
    assert bot.restart_requested is False

    assert bot.role_manager is not None
    assert bot.role_discovery_service is not None
    assert bot.authorization_service is not None
    assert bot.say_service is not None
    assert bot.role_classifier is not None
    assert bot.adult_access_classifier is not None

    assert bot.database is not None
    assert bot.database_schema is not None
    assert bot.database_status_service is not None
    assert bot.database_ownership_repository is not None
    assert bot.database_ownership_service is not None

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
        guild=bot_module.discord.Object(
            id=123,
        ),
    )

    assert commands == []


@pytest.mark.asyncio
async def test_setup_hook_resolves_identity_registers_commands_and_syncs(
    monkeypatch,
    tmp_path,
) -> None:
    """Expose the complete command set for a valid owned database."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    identity = _create_runtime_identity()

    resolve = AsyncMock(
        return_value=identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    status_check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=8,
            target_version=8,
        )
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
    )

    validate = AsyncMock()

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
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

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        789,
    )

    assert bot.runtime_identity == identity

    commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=123,
            ),
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

    admin_group = commands["experimentum"]

    assert {command.name for command in admin_group.commands} == {
        "roles",
        "catalog",
        "report",
        "database",
        "guild",
        "restart",
    }

    sync.assert_awaited_once()

    guild = sync.await_args.kwargs["guild"]

    assert guild.id == 123


@pytest.mark.asyncio
async def test_setup_hook_uses_maintenance_commands_when_database_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    """Expose only recovery commands when the database is missing."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    identity = _create_runtime_identity(
        bot_display_name="Experimentum",
    )

    resolve = AsyncMock(
        return_value=identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    validate = AsyncMock()

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
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

    validate.assert_not_awaited()

    assert bot.runtime_identity == identity

    commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=123,
            ),
        )
    }

    assert set(commands) == {
        "say",
        "experimentum",
    }

    admin_group = commands["experimentum"]

    assert {command.name for command in admin_group.commands} == {
        "database",
        "restart",
    }

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    assert {command.name for command in database_group.commands} == {
        "status",
        "initialize",
        "migrate",
        "bind",
    }

    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_uses_maintenance_commands_when_database_is_unbound(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep an unbound V8 database in maintenance mode."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    identity = _create_runtime_identity(
        bot_display_name="Experimentum",
    )

    resolve = AsyncMock(
        return_value=identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    status_check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=8,
            target_version=8,
        )
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
    )

    validate = AsyncMock(
        side_effect=DatabaseOwnershipUnboundError(
            "Database is not bound to a Discord application."
        )
    )

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
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

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        789,
    )

    assert bot.runtime_identity == identity

    commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=123,
            ),
        )
    }

    assert set(commands) == {
        "say",
        "experimentum",
    }

    admin_group = commands["experimentum"]

    assert {command.name for command in admin_group.commands} == {
        "database",
        "restart",
    }

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    assert {command.name for command in database_group.commands} == {
        "status",
        "initialize",
        "migrate",
        "bind",
    }

    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_rejects_database_owned_by_another_application(
    monkeypatch,
    tmp_path,
) -> None:
    """Fail closed when another Discord application owns the database."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    identity = _create_runtime_identity(
        application_id=999,
        application_name="Intruder",
        bot_display_name="Intruder",
        admin_command_name="intruder",
    )

    resolve = AsyncMock(
        return_value=identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve",
        resolve,
    )

    status_check = AsyncMock(
        return_value=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=8,
            target_version=8,
        )
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
    )

    validate = AsyncMock(
        side_effect=DatabaseOwnershipMismatchError(
            "Database belongs to another Discord application."
        )
    )

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
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
        DatabaseOwnershipMismatchError,
        match="belongs to another Discord application",
    ):
        await bot.setup_hook()

    resolve.assert_awaited_once_with(
        bot,
        123,
    )

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        999,
    )

    sync.assert_not_awaited()

    assert bot.runtime_identity is None

    commands = bot.tree.get_commands(
        guild=bot_module.discord.Object(
            id=123,
        ),
    )

    assert commands == []


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

    status_check = AsyncMock()

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
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
    status_check.assert_not_awaited()
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

    status_check = AsyncMock()

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
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
    status_check.assert_not_awaited()
    sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_restart_closes_client(
    monkeypatch,
    tmp_path,
) -> None:
    """Store restart context before closing Discord."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    close = AsyncMock()

    monkeypatch.setattr(
        bot,
        "close",
        close,
    )

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
    )

    assert bot.restart_requested is False
    assert bot.pending_restart_request is None

    await bot.request_restart(
        restart_request,
    )

    assert bot.restart_requested is True
    assert bot.pending_restart_request == restart_request

    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_complete_restart_feedback_edits_original_response(
    monkeypatch,
    tmp_path,
) -> None:
    """Mark the original ephemeral Discord response as completed."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
    )

    bot = ClavigerBot(
        startup_restart_request=restart_request,
    )

    request = AsyncMock()

    monkeypatch.setattr(
        bot.http,
        "request",
        request,
    )

    await bot._complete_restart_feedback()

    request.assert_awaited_once()

    route = request.await_args.args[0]

    assert route.method == "PATCH"

    assert request.await_args.kwargs["json"] == {
        "content": (
            "Redémarrage terminé. L'application est de nouveau opérationnelle."
        ),
        "allowed_mentions": {
            "parse": [],
        },
    }
