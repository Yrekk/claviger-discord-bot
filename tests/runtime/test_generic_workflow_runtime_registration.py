from pathlib import Path

from claviger import bot as bot_module
from claviger.bot import ClavigerBot
from claviger.database.status import DatabaseState, DatabaseStatus
from claviger.models.runtime.discord_application_identity_model import (
    DiscordApplicationIdentity,
)
from claviger.models.runtime.discord_guild_identity_model import DiscordGuildIdentity
from claviger.models.workflows.workflow_definition_model import WorkflowDefinition


def _bot(
    monkeypatch,
    tmp_path: Path,
) -> ClavigerBot:
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
    return ClavigerBot()


def test_register_guild_commands_adds_enabled_persisted_workflows(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Expose persisted workflow command names in the guild-local tree."""

    bot = _bot(
        monkeypatch,
        tmp_path,
    )

    workflow = WorkflowDefinition(
        guild_id=123,
        workflow_key="cine",
        command_name="cine",
        command_description="Configure tes choix cinéma.",
        title="Cinéma",
        description=None,
        policy_key="cine",
        channel_mode="restricted",
        sort_order=0,
        enabled=True,
        channel_ids=(201,),
        catalogs=(),
        primary_role_id=300,
    )

    bot._register_guild_commands(
        DiscordApplicationIdentity(
            application_id=789,
            application_name="Experimentum",
            bot_user_id=456,
            admin_command_name="experimentum",
        ),
        DiscordGuildIdentity(
            guild_id=123,
            bot_display_name="Experimentum",
        ),
        database_status=DatabaseStatus(
            state=DatabaseState.READY,
            current_version=12,
            target_version=12,
        ),
        database_operational=True,
        guild_ready=True,
        admin_command_channel_id=202,
        workflow_definitions=(
            workflow,
        ),
    )

    commands = {
        command.name
        for command in bot.tree.get_commands(
            guild=bot_module.discord.Object(
                id=123,
            )
        )
    }

    assert commands == {
        "say",
        "cine",
        "experimentum",
    }
