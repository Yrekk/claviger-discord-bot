import logging
from unittest.mock import Mock

from claviger import main as main_module


def test_configure_logging_uses_configured_claviger_level(
    monkeypatch,
) -> None:
    """Configure Claviger independently from Discord logging."""

    setup_logging = Mock()

    monkeypatch.setattr(
        main_module.discord.utils,
        "setup_logging",
        setup_logging,
    )

    monkeypatch.setattr(
        main_module,
        "get_log_level",
        lambda: logging.DEBUG,
    )

    claviger_logger = logging.getLogger(
        "claviger",
    )
    discord_logger = logging.getLogger(
        "discord",
    )

    original_claviger_level = claviger_logger.level
    original_discord_level = discord_logger.level

    try:
        main_module.configure_logging()

        setup_logging.assert_called_once_with(
            level=logging.INFO,
            root=True,
        )

        assert claviger_logger.level == logging.DEBUG
        assert discord_logger.level == logging.INFO

    finally:
        claviger_logger.setLevel(
            original_claviger_level,
        )

        discord_logger.setLevel(
            original_discord_level,
        )
