from unittest.mock import Mock, call

from claviger import main as main_module
from claviger.models.runtime_restart_model import RuntimeRestartRequest


def test_main_starts_bot_with_discord_token(monkeypatch) -> None:
    """Start ClavigerBot with the configured Discord token."""

    fake_bot = Mock()
    fake_bot.restart_requested = False

    bot_factory = Mock(
        return_value=fake_bot,
    )

    monkeypatch.setattr(
        main_module,
        "get_discord_token",
        lambda: "test-token",
    )

    monkeypatch.setattr(
        main_module,
        "ClavigerBot",
        bot_factory,
    )

    main_module.main()

    bot_factory.assert_called_once_with(
        startup_restart_request=None,
    )

    fake_bot.run.assert_called_once_with(
        "test-token",
    )


def test_main_recreates_bot_after_restart_request(monkeypatch) -> None:
    """Transfer restart context to a fresh bot instance."""

    restart_request = RuntimeRestartRequest(
        application_id=789,
        interaction_token="restart-token",
    )

    first_bot = Mock()
    first_bot.restart_requested = True
    first_bot.pending_restart_request = restart_request

    second_bot = Mock()
    second_bot.restart_requested = False

    bot_factory = Mock(
        side_effect=[
            first_bot,
            second_bot,
        ]
    )

    monkeypatch.setattr(
        main_module,
        "get_discord_token",
        lambda: "test-token",
    )

    monkeypatch.setattr(
        main_module,
        "ClavigerBot",
        bot_factory,
    )

    main_module.main()

    assert bot_factory.call_args_list == [
        call(
            startup_restart_request=None,
        ),
        call(
            startup_restart_request=restart_request,
        ),
    ]

    first_bot.run.assert_called_once_with(
        "test-token",
    )

    second_bot.run.assert_called_once_with(
        "test-token",
    )
