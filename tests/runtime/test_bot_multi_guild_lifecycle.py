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
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)

# Models
from claviger.models.runtime.application_runtime_state_model import (
    ApplicationRuntimeMode,
    ApplicationRuntimeState,
    DatabaseOwnershipState,
)
from claviger.models.runtime.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.runtime.discord_guild_identity_model import (
    DiscordGuildIdentity,
)
from claviger.models.runtime.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
    GuildConfigurationReadinessState,
)
from claviger.models.runtime.guild_runtime_state_model import GuildRuntimeState
from claviger.models.runtime.runtime_restart_model import RuntimeRestartRequest


def _patch_bot_configuration(
    monkeypatch,
    tmp_path,
) -> None:
    """Provide deterministic environment-backed configuration for lifecycle tests."""

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


def _application_runtime_state(
    database_status: DatabaseStatus | None = None,
) -> ApplicationRuntimeState:
    """Create a normal application runtime state for lifecycle tests."""

    return ApplicationRuntimeState(
        mode=ApplicationRuntimeMode.NORMAL,
        database_status=database_status or _ready_database_status(),
        database_ownership_state=DatabaseOwnershipState.VALID,
    )


def _ready_guild_readiness(
    guild_id: int,
) -> GuildConfigurationReadiness:
    """Create complete ADMIN readiness unique to one guild."""

    configuration = GuildAdminConfiguration(
        guild_id=guild_id,
        category_id=(guild_id * 10) + 1,
        command_channel_id=(guild_id * 10) + 2,
        activity_forum_id=(guild_id * 10) + 3,
        error_forum_id=(guild_id * 10) + 4,
    )

    return GuildConfigurationReadiness(
        guild_id=guild_id,
        state=GuildConfigurationReadinessState.READY,
        configuration=configuration,
    )


def _missing_guild_readiness(
    guild_id: int,
) -> GuildConfigurationReadiness:
    """Create readiness for a guild with no persisted ADMIN configuration."""

    return GuildConfigurationReadiness(
        guild_id=guild_id,
        state=GuildConfigurationReadinessState.ADMIN_CONFIGURATION_MISSING,
        configuration=None,
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


def _guild_command_names(
    bot: ClavigerBot,
    guild_id: int,
) -> set[str]:
    """Return local application-command names registered for one guild."""

    return {
        command.name
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=guild_id,
            ),
        )
    }


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
    bot.application_runtime_state = _application_runtime_state()

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
    bot.application_runtime_state = _application_runtime_state(
        database_status,
    )

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
        database_ownership_state=DatabaseOwnershipState.VALID,
        previous_command_tree_signature="existing-tree",
    )


@pytest.mark.asyncio
async def test_configure_runtime_guild_uses_matching_restart_signature(
    monkeypatch,
    tmp_path,
) -> None:
    """Restore the previous signature belonging to the configured guild."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
        guild_command_tree_signatures=(
            (
                123,
                "guild-123-tree",
            ),
            (
                999,
                "guild-999-tree",
            ),
        ),
    )

    bot = ClavigerBot(
        startup_restart_request=restart_request,
    )

    application_identity = _application_identity()
    database_status = _ready_database_status()

    bot.application_identity = application_identity
    bot.application_runtime_state = _application_runtime_state(
        database_status,
    )

    replacement_state = _guild_runtime_state(
        999,
        "rebuilt-guild-999-tree",
    )

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
    )

    assert result is replacement_state

    configure.assert_awaited_once_with(
        application_identity,
        999,
        database_status=database_status,
        database_operational=True,
        database_ownership_state=DatabaseOwnershipState.VALID,
        previous_command_tree_signature="guild-999-tree",
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
    bot.application_runtime_state = _application_runtime_state()

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
async def test_guild_events_configure_join_and_available_without_forced_refresh(
    monkeypatch,
    tmp_path,
) -> None:
    """Use normal configuration for joins and availability events."""

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
    assert configure.await_args_list[1].kwargs == {}


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


@pytest.mark.asyncio
async def test_multi_guild_runtime_keeps_guild_state_isolated_across_lifecycle(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep ready, unconfigured and newly joined guilds fully isolated."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    bot.application_identity = _application_identity()
    bot.application_runtime_state = _application_runtime_state()

    guild_identities = {
        123: DiscordGuildIdentity(
            guild_id=123,
            bot_display_name="Experimentum Guild A",
        ),
        999: DiscordGuildIdentity(
            guild_id=999,
            bot_display_name="Experimentum Guild B",
        ),
        555: DiscordGuildIdentity(
            guild_id=555,
            bot_display_name="Experimentum Guild C",
        ),
    }

    readiness_by_guild = {
        123: _ready_guild_readiness(
            123,
        ),
        999: _missing_guild_readiness(
            999,
        ),
        555: _missing_guild_readiness(
            555,
        ),
    }

    resolve_guild = AsyncMock(
        side_effect=lambda client, guild_id: guild_identities[guild_id],
    )

    readiness_inspect = AsyncMock(
        side_effect=lambda guild_id: readiness_by_guild[guild_id],
    )

    sync = AsyncMock(
        return_value=[],
    )

    list_workflows = AsyncMock(
        return_value=(),
    )

    monkeypatch.setattr(
        bot.workflow_definition_repository,
        "list_for_guild",
        list_workflows,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_guild",
        resolve_guild,
    )

    monkeypatch.setattr(
        bot.guild_configuration_readiness_service,
        "inspect",
        readiness_inspect,
    )

    monkeypatch.setattr(
        bot.tree,
        "sync",
        sync,
    )

    bot._connection._guilds = {
        123: SimpleNamespace(
            id=123,
            unavailable=False,
        ),
        999: SimpleNamespace(
            id=999,
            unavailable=False,
        ),
    }

    # Guild A is ready while Guild B has never completed ADMIN configuration.
    await bot.on_ready()

    assert set(bot.guild_runtime_states) == {
        123,
        999,
    }

    guild_a_initial_state = bot.guild_runtime_states[123]
    guild_b_initial_state = bot.guild_runtime_states[999]

    assert guild_a_initial_state.identity == guild_identities[123]
    assert guild_a_initial_state.readiness == readiness_by_guild[123]
    assert guild_a_initial_state.readiness is not None
    assert guild_a_initial_state.readiness.is_ready is True

    assert guild_b_initial_state.identity == guild_identities[999]
    assert guild_b_initial_state.readiness == readiness_by_guild[999]
    assert guild_b_initial_state.readiness is not None
    assert guild_b_initial_state.readiness.is_ready is False

    # This scenario returns no persisted workflow for either guild.
    assert _guild_command_names(
        bot,
        123,
    ) == {
        "say",
        "experimentum",
    }

    assert _guild_command_names(
        bot,
        999,
    ) == {
        "say",
        "experimentum",
    }

    guild_a_configuration = guild_a_initial_state.readiness.configuration

    assert guild_a_configuration is not None
    assert guild_a_configuration.guild_id == 123
    assert guild_a_configuration.command_channel_id == 1232
    assert guild_a_configuration.error_forum_id == 1234

    # Guild B completes configuration. Rebuilding B must not mutate Guild A.
    readiness_by_guild[999] = _ready_guild_readiness(
        999,
    )

    await bot._configure_runtime_guild(
        999,
        force=True,
    )

    guild_a_after_b_configuration = bot.guild_runtime_states[123]
    guild_b_ready_state = bot.guild_runtime_states[999]

    assert guild_a_after_b_configuration is guild_a_initial_state
    assert guild_b_ready_state is not guild_b_initial_state

    assert guild_b_ready_state.readiness == readiness_by_guild[999]
    assert guild_b_ready_state.readiness is not None
    assert guild_b_ready_state.readiness.is_ready is True

    guild_b_configuration = guild_b_ready_state.readiness.configuration

    assert guild_b_configuration is not None
    assert guild_b_configuration.guild_id == 999
    assert guild_b_configuration.command_channel_id == 9992
    assert guild_b_configuration.error_forum_id == 9994

    assert guild_a_configuration.command_channel_id == 1232
    assert guild_a_configuration.error_forum_id == 1234

    assert _guild_command_names(
        bot,
        123,
    ) == {
        "say",
        "experimentum",
    }

    assert _guild_command_names(
        bot,
        999,
    ) == {
        "say",
        "experimentum",
    }

    # Guild C joins while the application is already running. It must receive
    # only its own recovery/configuration tree while A and B remain untouched.
    await bot.on_guild_join(
        SimpleNamespace(
            id=555,
        ),
    )

    assert set(bot.guild_runtime_states) == {
        123,
        999,
        555,
    }

    assert bot.guild_runtime_states[123] is guild_a_initial_state
    assert bot.guild_runtime_states[999] is guild_b_ready_state

    guild_c_state = bot.guild_runtime_states[555]

    assert guild_c_state.identity == guild_identities[555]
    assert guild_c_state.readiness == readiness_by_guild[555]
    assert guild_c_state.readiness is not None
    assert guild_c_state.readiness.is_ready is False

    assert _guild_command_names(
        bot,
        555,
    ) == {
        "say",
        "experimentum",
    }

    assert _guild_command_names(
        bot,
        123,
    ) == {
        "say",
        "experimentum",
    }

    assert _guild_command_names(
        bot,
        999,
    ) == {
        "say",
        "experimentum",
    }

    assert resolve_guild.await_count == 4
    assert readiness_inspect.await_count == 4
    assert list_workflows.await_count == 2
    assert sync.await_count == 4
