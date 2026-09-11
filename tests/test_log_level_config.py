import logging
from pathlib import Path

import pytest

from claviger import config


def _write_logging_environment(
    tmp_path: Path,
    *,
    log_level: str | None,
) -> Path:
    """Create a minimal local environment for logging tests."""

    selector_path = tmp_path / ".env"
    environment_path = tmp_path / ".env.development"

    selector_path.write_text(
        "CLAVIGER_ENV=development\n",
        encoding="utf-8",
    )

    lines = [
        "CLAVIGER_ENV=development",
    ]

    if log_level is not None:
        lines.append(f"CLAVIGER_LOG_LEVEL={log_level}")

    environment_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    return selector_path


def test_log_level_defaults_to_info(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Use INFO when no explicit application log level is configured."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = _write_logging_environment(
        tmp_path,
        log_level=None,
    )

    assert (
        config.get_log_level(
            selector_path,
        )
        == logging.INFO
    )


def test_debug_log_level_is_normalized(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Accept a case-insensitive DEBUG log level."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = _write_logging_environment(
        tmp_path,
        log_level="debug",
    )

    assert (
        config.get_log_level(
            selector_path,
        )
        == logging.DEBUG
    )


def test_invalid_log_level_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Reject unsupported application log levels."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = _write_logging_environment(
        tmp_path,
        log_level="verbose",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported CLAVIGER_LOG_LEVEL",
    ):
        config.get_log_level(
            selector_path,
        )
