from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

# Third-party
import pytest

# Runtime
from claviger import bot as bot_module
from claviger.bot import ClavigerBot

# Database
from claviger.database.schema import CURRENT_SCHEMA_VERSION
from claviger.database.status import (
    DatabaseState,
    DatabaseStatus,
)

# Models
from claviger.models.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
from claviger.models.guild_runtime_state_model import GuildRuntimeState


def _patch_bot_configuration(
    monkeypatch,
    tmp_path,
) -> None:
    """Provide deterministic legacy runtime configuration for lifecycle tests."""

    monkeypatch.setattr(
        bot_module,
        "get_discord_guild_id",
        lambda: 123,
    )

    monkeypatch.setattr(
        bot_module,
        "get_discord_bot_user_id",
        lambda: 456,
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


def _application_identity() -> DiscordApplicationIdentity:
    """Create deterministic application identity for lifecycle tests."""

    return DiscordApplicationIdentity(
        application_id=789,
        application_name="Experimentum",
        bot_user_id=456,
        admin_command_name="experimentum",
    )


def _ready_database_status() -> DatabaseStatus:
    """Create a READY application database status."""

    return DatabaseStatus(
        state=DatabaseState.READY,
        current_version=CURRENT_SCHEMA_VERSION,
        target_version=CURRENT_SCHEMA_VERSION,
    )


def _guild_runtime_state(
    guild_id: int,
    signature: str,
) -> GuildRuntimeState:
    """Create deterministic registered runtime state for one guild."""

    return GuildRuntimeState(
        identity=DiscordGuildIdentity(
            guild_id=guild_id,
            bot_display_name=f"Experimentum {guild_id}",
        ),
        readiness=None,
        command_tree_signature=signature,
    )


@pytest.mark.asyncio
async def test_configure_runtime_guild_reuses_existing_state(
    monkeypatch,
    tmp_path,
) -> None:
    """Do not rebuild an already configured guild during repeated events."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    bot.application_identity = _application_identity()
    bot.database_status = _ready_database_status()
    bot.database_operational = True

    existing_state = _guild_runtime_state(
        999,
        "existing-tree",
    )

    bot.guild_runtime_states[999] = existing_state

    configure = AsyncMock()

    monkeypatch.setattr(
        bot,
        "_configure_guild",
        configure,
    )

    result = await bot._configure_runtime_guild(
        999,
    )

    assert result is existing_state
    configure.assert_not_awaited()


@pytest.mark.asyncio
async def test_configure_runtime_guild_force_rebuild_uses_previous_signature(
    monkeypatch,
    tmp_path,
) -> None:
    """Reuse the previous guild signature during forced reconfiguration."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    application_identity = _application_identity()
    database_status = _ready_database_status()

    bot.application_identity = application_identity
    bot.database_status = database_status
    bot.database_operational = True

    existing_state = _guild_runtime_state(
        999,
        "existing-tree",
    )

    replacement_state = _guild_runtime_state(
        999,
        "replacement-tree",
    )

    bot.guild_runtime_states[999] = existing_state

    configure = AsyncMock(
        return_value=replacement_state,
    )

    monkeypatch.setattr(
        bot,
        "_configure_guild",
        configure,
    )

    result = await bot._configure_runtime_guild(
        999,
        force=True,
    )

    assert result is replacement_state

    configure.assert_awaited_once_with(
        application_identity,
        999,
        database_status=database_status,
        database_operational=True,
        previous_command_tree_signature="existing-tree",
    )


@pytest.mark.asyncio
async def test_on_ready_configures_every_available_cached_guild(
    monkeypatch,
    tmp_path,
) -> None:
    """Configure cached guilds while ignoring temporarily unavailable ones."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    bot.application_identity = _application_identity()
    bot.database_status = _ready_database_status()
    bot.database_operational = True

    bot._connection._guilds = {
        123: SimpleNamespace(
            id=123,
            unavailable=False,
        ),
        999: SimpleNamespace(
            id=999,
            unavailable=False,
        ),
        555: SimpleNamespace(
            id=555,
            unavailable=True,
        ),
    }

    configure = AsyncMock()

    monkeypatch.setattr(
        bot,
        "_configure_runtime_guild",
        configure,
    )

    await bot.on_ready()

    configured_guild_ids = [call.args[0] for call in configure.await_args_list]

    assert configured_guild_ids == [
        123,
        999,
    ]


@pytest.mark.asyncio
async def test_guild_events_configure_join_and_force_available(
    monkeypatch,
    tmp_path,
) -> None:
    """Use normal configuration for joins and forced refresh for availability."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    configure = AsyncMock()

    monkeypatch.setattr(
        bot,
        "_configure_runtime_guild",
        configure,
    )

    guild = SimpleNamespace(
        id=999,
    )

    await bot.on_guild_join(
        guild,
    )

    await bot.on_guild_available(
        guild,
    )

    assert configure.await_count == 2

    assert configure.await_args_list[0].args == (999,)
    assert configure.await_args_list[0].kwargs == {}

    assert configure.await_args_list[1].args == (999,)
    assert configure.await_args_list[1].kwargs == {
        "force": True,
    }


@pytest.mark.asyncio
async def test_unavailable_and_removed_guilds_lose_runtime_state(
    monkeypatch,
    tmp_path,
) -> None:
    """Invalidate unavailable guilds and forget removed guild command trees."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    bot.guild_runtime_states[999] = _guild_runtime_state(
        999,
        "guild-999-tree",
    )

    bot.guild_runtime_states[888] = _guild_runtime_state(
        888,
        "guild-888-tree",
    )

    clear_commands = Mock()

    monkeypatch.setattr(
        bot.tree,
        "clear_commands",
        clear_commands,
    )

    await bot.on_guild_unavailable(
        SimpleNamespace(
            id=999,
        ),
    )

    assert 999 not in bot.guild_runtime_states
    assert 888 in bot.guild_runtime_states

    await bot.on_guild_remove(
        SimpleNamespace(
            id=888,
        ),
    )

    assert 888 not in bot.guild_runtime_states

    clear_commands.assert_called_once()

    removed_guild = clear_commands.call_args.kwargs["guild"]

    assert removed_guild.id == 888
