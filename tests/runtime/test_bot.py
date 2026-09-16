# Standard library
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
from claviger.models.admin.guild_admin_configuration_model import (
    GuildAdminConfiguration,
)
from claviger.models.guild_configuration_readiness_model import (
    GuildConfigurationReadiness,
    GuildConfigurationReadinessState,
)
from claviger.models.guild_runtime_state_model import GuildRuntimeState
from claviger.models.runtime_restart_model import RuntimeRestartRequest

# Services
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
    """Provide deterministic environment-backed runtime configuration.

    Args:
        monkeypatch:
            Pytest monkeypatch fixture used to replace configuration getters.

        tmp_path:
            Temporary test directory used as the fake SQLite location.

        bot_user_id:
            Expected authenticated Discord bot user ID.

    Returns:
        None:
            Runtime configuration getters are patched for one test.
    """

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


def _create_application_identity(
    *,
    application_id: int = 789,
    application_name: str = "Experimentum",
    bot_user_id: int = 456,
    admin_command_name: str = "experimentum",
) -> DiscordApplicationIdentity:
    """Create a deterministic application-wide Discord identity.

    Args:
        application_id:
            Discord application snowflake.

        application_name:
            Human-readable Discord application name.

        bot_user_id:
            Authenticated bot user snowflake.

        admin_command_name:
            Normalized dynamic administrative slash-command root.

    Returns:
        DiscordApplicationIdentity:
            Application identity suitable for runtime composition tests.
    """

    return DiscordApplicationIdentity(
        application_id=application_id,
        application_name=application_name,
        bot_user_id=bot_user_id,
        admin_command_name=admin_command_name,
    )


def _create_guild_identity(
    *,
    guild_id: int = 123,
    bot_display_name: str = "Vespera DEV",
) -> DiscordGuildIdentity:
    """Create deterministic identity values specific to one guild.

    Args:
        guild_id:
            Discord guild snowflake.

        bot_display_name:
            Display name used by the bot inside this guild.

    Returns:
        DiscordGuildIdentity:
            Guild-specific identity suitable for runtime tests.
    """

    return DiscordGuildIdentity(
        guild_id=guild_id,
        bot_display_name=bot_display_name,
    )


def _ready_database_status() -> DatabaseStatus:
    """Create a READY status matching the current schema version.

    Returns:
        DatabaseStatus:
            Database status whose current and target versions always follow
            ``CURRENT_SCHEMA_VERSION``.
    """

    return DatabaseStatus(
        state=DatabaseState.READY,
        current_version=CURRENT_SCHEMA_VERSION,
        target_version=CURRENT_SCHEMA_VERSION,
    )


def _missing_database_status() -> DatabaseStatus:
    """Create a deterministic MISSING database status.

    Returns:
        DatabaseStatus:
            Missing database state targeting the current schema version.
    """

    return DatabaseStatus(
        state=DatabaseState.MISSING,
        current_version=None,
        target_version=CURRENT_SCHEMA_VERSION,
    )


def _create_ready_guild_readiness(
    *,
    guild_id: int = 123,
) -> GuildConfigurationReadiness:
    """Create a complete persisted ADMIN readiness result.

    Args:
        guild_id:
            Discord guild snowflake represented by the configuration.

    Returns:
        GuildConfigurationReadiness:
            READY result backed by complete ADMIN routing.
    """

    configuration = GuildAdminConfiguration(
        guild_id=guild_id,
        category_id=1000,
        command_channel_id=1001,
        activity_forum_id=1002,
        error_forum_id=1003,
    )

    return GuildConfigurationReadiness(
        guild_id=guild_id,
        state=GuildConfigurationReadinessState.READY,
        configuration=configuration,
    )


def _create_missing_guild_readiness(
    *,
    guild_id: int = 123,
) -> GuildConfigurationReadiness:
    """Create readiness for a guild unknown to persistent ADMIN routing.

    Args:
        guild_id:
            Discord guild snowflake represented by the readiness result.

    Returns:
        GuildConfigurationReadiness:
            Non-ready result indicating that no ADMIN configuration exists.
    """

    return GuildConfigurationReadiness(
        guild_id=guild_id,
        state=(GuildConfigurationReadinessState.ADMIN_CONFIGURATION_MISSING),
        configuration=None,
    )


def _patch_identity_resolution(
    monkeypatch,
    bot: ClavigerBot,
    *,
    application_identity: DiscordApplicationIdentity | None = None,
    guild_identity: DiscordGuildIdentity | None = None,
) -> tuple[AsyncMock, AsyncMock]:
    """Patch separate application and guild identity resolution.

    Args:
        monkeypatch:
            Pytest monkeypatch fixture.

        bot:
            Claviger runtime whose identity service must be patched.

        application_identity:
            Optional application identity returned by the mocked resolver.

        guild_identity:
            Optional guild identity returned by the mocked resolver.

    Returns:
        tuple[AsyncMock, AsyncMock]:
            Application resolver mock followed by guild resolver mock.
    """

    if application_identity is None:
        application_identity = _create_application_identity()

    if guild_identity is None:
        guild_identity = _create_guild_identity()

    resolve_application = AsyncMock(
        return_value=application_identity,
    )

    resolve_guild = AsyncMock(
        return_value=guild_identity,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_application",
        resolve_application,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_guild",
        resolve_guild,
    )

    return resolve_application, resolve_guild


def _patch_readiness_inspection(
    monkeypatch,
    bot: ClavigerBot,
    *,
    readiness: GuildConfigurationReadiness | None = None,
) -> AsyncMock:
    """Patch guild readiness inspection.

    Args:
        monkeypatch:
            Pytest monkeypatch fixture.

        bot:
            Claviger runtime whose readiness service must be patched.

        readiness:
            Optional result returned by the mocked readiness service. Defaults
            to a complete READY guild.

    Returns:
        AsyncMock:
            Mocked asynchronous ``inspect`` operation.
    """

    if readiness is None:
        readiness = _create_ready_guild_readiness()

    inspect = AsyncMock(
        return_value=readiness,
    )

    monkeypatch.setattr(
        bot.guild_configuration_readiness_service,
        "inspect",
        inspect,
    )

    return inspect


def _cache_available_guild(
    bot: ClavigerBot,
    *,
    guild_id: int = 123,
) -> None:
    """Expose one available guild through the mocked Discord gateway cache.

    Args:
        bot:
            Claviger runtime whose Discord guild cache must be prepared.

        guild_id:
            Discord guild snowflake exposed as currently available.

    Returns:
        None:
            The mocked discord.py connection cache is updated in place.
    """

    bot._connection._guilds = {
        guild_id: SimpleNamespace(
            id=guild_id,
            unavailable=False,
        ),
    }


def test_claviger_bot_composition(
    monkeypatch,
    tmp_path,
) -> None:
    """Build generic runtime composition without specialized workflows."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    assert bot.expected_bot_user_id == 456
    assert not hasattr(bot, "guild_id")
    assert not hasattr(bot, "guild_identity")
    assert not hasattr(bot, "guild_readiness")
    assert not hasattr(bot, "command_tree_signature")

    assert bot.discord_identity_service is not None
    assert bot.application_identity is None
    assert bot.guild_runtime_states == {}
    assert bot.restart_requested is False

    assert bot.policy_resolver.fallback_guild_id == 123
    assert bot.guild_policy_bootstrap_service.fallback_guild_id == 123

    assert bot.role_discovery_service is not None
    assert bot.authorization_service is not None
    assert bot.say_service is not None

    assert bot.database is not None
    assert bot.database_schema is not None
    assert bot.database_status_service is not None
    assert bot.database_ownership_repository is not None
    assert bot.database_ownership_service is not None

    assert bot.guild_policy_repository is not None
    assert bot.policy_resolver is not None
    assert bot.guild_policy_bootstrap_service is not None

    assert bot.guild_admin_configuration_repository is not None
    assert bot.guild_configuration_readiness_service is not None
    assert bot.admin_structure_discovery_service is not None
    assert bot.admin_configuration_reconciliation_service is not None
    assert bot.admin_structure_provisioning_service is not None
    assert bot.admin_configuration_coordinator_service is not None

    assert bot.workflow_configuration_repository is not None
    assert bot.workflow_configuration_validation_service is not None
    assert bot.workflow_structure_discovery_service is not None
    assert bot.workflow_configuration_reconciliation_service is not None
    assert bot.workflow_structure_provisioning_service is not None
    assert bot.workflow_configuration_coordinator_service is not None

    assert bot.guild_configuration_inspection_service is not None
    assert bot.report_service is not None

    legacy_attributes = (
        "role_manager",
        "role_classifier",
        "adult_access_classifier",
        "interest_catalog_repository",
        "access_catalog_repository",
        "catalog_registry",
        "catalog_sync_planner",
        "catalog_sync_coordinator_service",
        "catalog_next_coordinator_service",
        "member_interest_questionnaire_service",
        "member_role_planner_service",
        "member_role_executor_service",
        "member_workflow_coordinator_service",
        "adult_access_workflow_service",
        "adult_access_questionnaire_service",
        "noctis_role_planner_service",
        "noctis_role_executor_service",
        "noctis_workflow_coordinator_service",
    )

    for attribute_name in legacy_attributes:
        assert not hasattr(bot, attribute_name)

    commands = bot.tree.get_commands(
        guild=bot_module.discord.Object(
            id=123,
        ),
    )

    assert commands == []


def test_register_guild_commands_targets_supplied_guild_identity(
    monkeypatch,
    tmp_path,
) -> None:
    """Register commands only against the supplied guild identity."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    application_identity = _create_application_identity()

    guild_identity = _create_guild_identity(
        guild_id=999,
        bot_display_name="Experimentum Server B",
    )

    bot._register_guild_commands(
        application_identity,
        guild_identity,
        database_status=_missing_database_status(),
        database_operational=False,
        guild_ready=False,
        admin_command_channel_id=None,
    )

    source_guild_commands = bot.tree.get_commands(
        guild=bot_module.discord.Object(
            id=123,
        ),
    )

    target_guild_commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=999,
            ),
        )
    }

    assert source_guild_commands == []

    assert set(target_guild_commands) == {
        "say",
        "experimentum",
    }

    assert target_guild_commands["say"].description == (
        "Fait envoyer un message par Experimentum Server B dans le salon actuel."
    )

    admin_group = target_guild_commands["experimentum"]

    assert {command.name for command in admin_group.commands} == {
        "database",
        "restart",
        "config-server",
        "config",
    }


@pytest.mark.asyncio
async def test_configure_guild_builds_and_stores_supplied_guild_runtime_state(
    monkeypatch,
    tmp_path,
) -> None:
    """Configure one supplied guild independently from legacy runtime state."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    application_identity = _create_application_identity()

    guild_identity = _create_guild_identity(
        guild_id=999,
        bot_display_name="Experimentum Server B",
    )

    resolve_application, resolve_guild = _patch_identity_resolution(
        monkeypatch,
        bot,
        application_identity=application_identity,
        guild_identity=guild_identity,
    )

    readiness = _create_ready_guild_readiness(
        guild_id=999,
    )

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
        readiness=readiness,
    )

    sync = AsyncMock(
        return_value=[],
    )

    monkeypatch.setattr(
        bot.tree,
        "sync",
        sync,
    )

    runtime_state = await bot._configure_guild(
        application_identity,
        999,
        database_status=_ready_database_status(),
        database_operational=True,
    )

    resolve_application.assert_not_awaited()

    resolve_guild.assert_awaited_once_with(
        bot,
        999,
    )

    readiness_inspect.assert_awaited_once_with(
        999,
    )

    sync.assert_awaited_once()

    synced_guild = sync.await_args.kwargs["guild"]

    assert synced_guild.id == 999

    assert runtime_state.identity == guild_identity
    assert runtime_state.readiness == readiness
    assert runtime_state.command_tree_signature

    assert bot.guild_runtime_states == {
        999: runtime_state,
    }

    # Low-level guild configuration remains independent from application
    # startup state and stores guild-specific data only in the runtime registry.
    assert bot.application_identity is None
    assert not hasattr(bot, "guild_identity")
    assert not hasattr(bot, "guild_readiness")
    assert not hasattr(bot, "command_tree_signature")


@pytest.mark.asyncio
async def test_setup_hook_prepares_application_before_ready_configures_guild(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep setup application-only before ready configures cached guilds."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    application_identity = _create_application_identity()
    guild_identity = _create_guild_identity()

    resolve_application, resolve_guild = _patch_identity_resolution(
        monkeypatch,
        bot,
        application_identity=application_identity,
        guild_identity=guild_identity,
    )

    database_status = _ready_database_status()

    status_check = AsyncMock(
        return_value=database_status,
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

    readiness = _create_ready_guild_readiness()

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
        readiness=readiness,
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

    resolve_application.assert_awaited_once_with(
        bot,
    )

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        789,
    )

    resolve_guild.assert_not_awaited()
    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()

    assert bot.application_identity == application_identity
    assert bot.database_status == database_status
    assert bot.database_operational is True
    assert bot.guild_runtime_states == {}

    commands_before_ready = bot.tree.get_commands(
        guild=bot_module.discord.Object(
            id=123,
        ),
    )

    assert commands_before_ready == []

    _cache_available_guild(
        bot,
        guild_id=123,
    )

    await bot.on_ready()

    resolve_guild.assert_awaited_once_with(
        bot,
        123,
    )

    readiness_inspect.assert_awaited_once_with(
        123,
    )

    assert 123 in bot.guild_runtime_states

    assert bot.guild_runtime_states[123].identity == guild_identity
    assert bot.guild_runtime_states[123].readiness == readiness

    commands = {
        command.name: command
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=123,
            ),
        )
    }

    # Specialized runtime commands are gone. Generic workflow commands will be
    # registered from persisted workflow definitions in the next runtime slice.
    assert set(commands) == {
        "say",
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

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    assert {command.name for command in database_group.commands} == {
        "status",
    }

    assert {command.name for command in admin_group.commands} == {
        "roles",
        "report",
        "database",
        "guild",
        "restart",
        "config-server",
        "config",
    }

    sync.assert_awaited_once()

    synced_guild = sync.await_args.kwargs["guild"]

    assert synced_guild.id == 123


@pytest.mark.asyncio
async def test_setup_hook_uses_configuration_commands_for_new_guild(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep an unconfigured guild in configuration-only mode."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    application_identity = _create_application_identity()
    guild_identity = _create_guild_identity()

    _patch_identity_resolution(
        monkeypatch,
        bot,
        application_identity=application_identity,
        guild_identity=guild_identity,
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        AsyncMock(
            return_value=_ready_database_status(),
        ),
    )

    validate = AsyncMock()

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
    )

    readiness = _create_missing_guild_readiness()

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
        readiness=readiness,
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

    validate.assert_awaited_once_with(
        789,
    )

    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()

    _cache_available_guild(
        bot,
        guild_id=123,
    )

    await bot.on_ready()

    readiness_inspect.assert_awaited_once_with(
        123,
    )

    runtime_state = bot.guild_runtime_states[123]

    assert runtime_state.readiness == readiness
    assert runtime_state.readiness.is_ready is False

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
        "config-server",
        "config",
    }

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    # The application DB itself is healthy, so it needs no initialize/bind
    # action. Only guild configuration remains incomplete.
    assert {command.name for command in database_group.commands} == {
        "status",
    }

    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_uses_maintenance_commands_when_database_is_missing(
    monkeypatch,
    tmp_path,
) -> None:
    """Expose application recovery commands when the database is missing."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    application_identity = _create_application_identity()

    guild_identity = _create_guild_identity(
        bot_display_name="Experimentum",
    )

    resolve_application, resolve_guild = _patch_identity_resolution(
        monkeypatch,
        bot,
        application_identity=application_identity,
        guild_identity=guild_identity,
    )

    validate = AsyncMock()

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        validate,
    )

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
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

    resolve_application.assert_awaited_once_with(
        bot,
    )

    resolve_guild.assert_not_awaited()
    validate.assert_not_awaited()
    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()

    assert bot.application_identity == application_identity
    assert bot.guild_runtime_states == {}

    _cache_available_guild(
        bot,
        guild_id=123,
    )

    await bot.on_ready()

    resolve_guild.assert_awaited_once_with(
        bot,
        123,
    )

    readiness_inspect.assert_not_awaited()

    runtime_state = bot.guild_runtime_states[123]

    assert runtime_state.identity == guild_identity
    assert runtime_state.readiness is None

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
        "config-server",
        "config",
    }

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    assert {command.name for command in database_group.commands} == {
        "status",
        "initialize",
    }

    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_uses_maintenance_commands_when_database_is_unbound(
    monkeypatch,
    tmp_path,
) -> None:
    """Keep an unbound application database in maintenance mode."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    application_identity = _create_application_identity()

    guild_identity = _create_guild_identity(
        bot_display_name="Experimentum",
    )

    resolve_application, resolve_guild = _patch_identity_resolution(
        monkeypatch,
        bot,
        application_identity=application_identity,
        guild_identity=guild_identity,
    )

    status_check = AsyncMock(
        return_value=_ready_database_status(),
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

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
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

    resolve_application.assert_awaited_once_with(
        bot,
    )

    resolve_guild.assert_not_awaited()

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        789,
    )

    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()

    assert bot.application_identity == application_identity
    assert bot.guild_runtime_states == {}

    _cache_available_guild(
        bot,
        guild_id=123,
    )

    await bot.on_ready()

    resolve_guild.assert_awaited_once_with(
        bot,
        123,
    )

    readiness_inspect.assert_not_awaited()

    runtime_state = bot.guild_runtime_states[123]

    assert runtime_state.identity == guild_identity
    assert runtime_state.readiness is None

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
        "config-server",
        "config",
    }

    database_group = admin_group.get_command(
        "database",
    )

    assert database_group is not None

    assert {command.name for command in database_group.commands} == {
        "status",
        "bind",
    }

    sync.assert_awaited_once()


@pytest.mark.asyncio
async def test_setup_hook_rejects_database_owned_by_another_application(
    monkeypatch,
    tmp_path,
) -> None:
    """Fail closed before guild work when another application owns the DB."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    application_identity = _create_application_identity(
        application_id=999,
        application_name="Intruder",
        admin_command_name="intruder",
    )

    resolve_application = AsyncMock(
        return_value=application_identity,
    )

    resolve_guild = AsyncMock()

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_application",
        resolve_application,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_guild",
        resolve_guild,
    )

    status_check = AsyncMock(
        return_value=_ready_database_status(),
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

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
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

    resolve_application.assert_awaited_once_with(
        bot,
    )

    resolve_guild.assert_not_awaited()
    readiness_inspect.assert_not_awaited()

    status_check.assert_awaited_once()

    validate.assert_awaited_once_with(
        999,
    )

    sync.assert_not_awaited()

    assert bot.application_identity is None
    assert bot.guild_runtime_states == {}

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
    """Never inspect DB or guild state for an unexpected Discord bot token."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = SimpleNamespace(
        id=999,
    )

    resolve_application = AsyncMock()
    resolve_guild = AsyncMock()

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_application",
        resolve_application,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_guild",
        resolve_guild,
    )

    status_check = AsyncMock()

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
    )

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
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
        match=("Authenticated Discord bot identity does not match configuration"),
    ):
        await bot.setup_hook()

    resolve_application.assert_not_awaited()
    resolve_guild.assert_not_awaited()
    status_check.assert_not_awaited()
    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_setup_hook_rejects_missing_authenticated_identity(
    monkeypatch,
    tmp_path,
) -> None:
    """Fail closed when Discord has no authenticated bot identity."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    bot = ClavigerBot()

    bot._connection.user = None

    resolve_application = AsyncMock()
    resolve_guild = AsyncMock()

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_application",
        resolve_application,
    )

    monkeypatch.setattr(
        bot.discord_identity_service,
        "resolve_guild",
        resolve_guild,
    )

    status_check = AsyncMock()

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        status_check,
    )

    readiness_inspect = _patch_readiness_inspection(
        monkeypatch,
        bot,
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

    resolve_application.assert_not_awaited()
    resolve_guild.assert_not_awaited()
    status_check.assert_not_awaited()
    readiness_inspect.assert_not_awaited()
    sync.assert_not_awaited()


@pytest.mark.asyncio
async def test_request_restart_closes_client(
    monkeypatch,
    tmp_path,
) -> None:
    """Store every guild command signature and close the current client."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
    )

    bot = ClavigerBot()

    bot.guild_runtime_states[123] = GuildRuntimeState(
        identity=_create_guild_identity(
            guild_id=123,
            bot_display_name="Experimentum Server A",
        ),
        readiness=None,
        command_tree_signature="guild-123-tree",
    )

    bot.guild_runtime_states[999] = GuildRuntimeState(
        identity=_create_guild_identity(
            guild_id=999,
            bot_display_name="Experimentum Server B",
        ),
        readiness=None,
        command_tree_signature="guild-999-tree",
    )

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

    assert bot.pending_restart_request == RuntimeRestartRequest(
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

    close.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_complete_restart_feedback_edits_original_response(
    monkeypatch,
    tmp_path,
) -> None:
    """Mark the original Discord restart response as completed."""

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


@pytest.mark.asyncio
async def test_restart_guild_configuration_skips_sync_when_tree_is_unchanged(
    monkeypatch,
    tmp_path,
) -> None:
    """Avoid Discord sync when restart rebuilds the same ready-guild tree."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
        guild_command_tree_signatures=(
            (
                123,
                "same-tree",
            ),
        ),
    )

    bot = ClavigerBot(
        startup_restart_request=restart_request,
    )

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    _patch_identity_resolution(
        monkeypatch,
        bot,
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        AsyncMock(
            return_value=_ready_database_status(),
        ),
    )

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        AsyncMock(),
    )

    _patch_readiness_inspection(
        monkeypatch,
        bot,
    )

    monkeypatch.setattr(
        bot,
        "_build_command_tree_signature",
        lambda guild: "same-tree",
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

    sync.assert_not_awaited()

    await bot._configure_runtime_guild(
        123,
    )

    sync.assert_not_awaited()

    assert bot.guild_runtime_states[123].command_tree_signature == "same-tree"


@pytest.mark.asyncio
async def test_restart_guild_configuration_resyncs_when_tree_changes(
    monkeypatch,
    tmp_path,
) -> None:
    """Synchronize Discord when restart rebuilds a different command tree."""

    _patch_bot_configuration(
        monkeypatch,
        tmp_path,
        bot_user_id=456,
    )

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
        guild_command_tree_signatures=(
            (
                123,
                "old-tree",
            ),
        ),
    )

    bot = ClavigerBot(
        startup_restart_request=restart_request,
    )

    bot._connection.user = SimpleNamespace(
        id=456,
    )

    _patch_identity_resolution(
        monkeypatch,
        bot,
    )

    monkeypatch.setattr(
        bot.database_status_service,
        "check",
        AsyncMock(
            return_value=_ready_database_status(),
        ),
    )

    monkeypatch.setattr(
        bot.database_ownership_service,
        "validate",
        AsyncMock(),
    )

    _patch_readiness_inspection(
        monkeypatch,
        bot,
    )

    monkeypatch.setattr(
        bot,
        "_build_command_tree_signature",
        lambda guild: "new-tree",
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

    sync.assert_not_awaited()

    await bot._configure_runtime_guild(
        123,
    )

    sync.assert_awaited_once()

    assert bot.guild_runtime_states[123].command_tree_signature == "new-tree"
