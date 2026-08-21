from unittest.mock import Mock

from claviger import main as main_module


def test_main_starts_bot_with_discord_token(monkeypatch) -> None:
    """Start ClavigerBot with the configured Discord token."""
    fake_bot = Mock()
    bot_factory = Mock(return_value=fake_bot)

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

    bot_factory.assert_called_once_with()
    fake_bot.run.assert_called_once_with("test-token")