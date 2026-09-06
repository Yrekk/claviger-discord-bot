from claviger import bot as bot_module
from claviger.bot import ClavigerBot


def test_claviger_bot_composition(monkeypatch, tmp_path) -> None:
    """Build the complete bot composition without starting Discord."""

    monkeypatch.setattr(
        bot_module,
        "get_discord_guild_id",
        lambda: 123,
    )

    monkeypatch.setattr(
        bot_module,
        "get_database_path",
        lambda: tmp_path / "claviger.db",
    )

    monkeypatch.setattr(
        bot_module,
        "get_admin_report_forum_id",
        lambda: None,
    )

    bot = ClavigerBot()

    assert bot.guild_id == 123

    assert bot.role_manager is not None
    assert bot.role_discovery_service is not None
    assert bot.authorization_service is not None
    assert bot.say_service is not None
    assert bot.role_classifier is not None

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

    commands = {
        command.name
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(id=123),
        )
    }

    assert "say" in commands
    assert "claviger" in commands
