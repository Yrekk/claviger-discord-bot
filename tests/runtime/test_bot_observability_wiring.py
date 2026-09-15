from claviger import bot as bot_module
from claviger.bot import ClavigerBot
from claviger.reporting.command_tree import ClavigerCommandTree
from claviger.services.guild_configuration_inspection_service import (
    GuildConfigurationInspectionService,
)


def test_bot_wires_command_tree_and_configuration_inspection(
    monkeypatch,
    tmp_path,
) -> None:
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

    bot = ClavigerBot()

    assert isinstance(
        bot.tree,
        ClavigerCommandTree,
    )
    assert isinstance(
        bot.guild_configuration_inspection_service,
        GuildConfigurationInspectionService,
    )
