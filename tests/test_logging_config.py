import logging
from unittest.mock import Mock

from claviger import main as main_module


def test_configure_logging_uses_root_logger(monkeypatch) -> None:
    """Configure logging for Discord and Claviger loggers."""

    setup_logging = Mock()

    monkeypatch.setattr(
        main_module.discord.utils,
        "setup_logging",
        setup_logging,
    )

    main_module.configure_logging()

    setup_logging.assert_called_once_with(
        level=logging.INFO,
        root=True,
    )
