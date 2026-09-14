from pathlib import Path

import pytest

from claviger import config


def _write_environment_file(
    path: Path,
    environment: str,
    *,
    token: str = "test-token",
    bot_user_id: str = "456",
    guild_id: str = "123",
    database_path: str = "data/test.db",
) -> None:
    """Write one complete test environment configuration."""

    path.write_text(
        "\n".join(
            (
                f"CLAVIGER_ENV={environment}",
                f"DISCORD_TOKEN={token}",
                f"DISCORD_BOT_USER_ID={bot_user_id}",
                f"DISCORD_GUILD_ID={guild_id}",
                f"DATABASE_PATH={database_path}",
                "",
            )
        ),
        encoding="utf-8",
    )


def _write_selector(
    path: Path,
    environment: str,
) -> None:
    """Write one local environment selector."""

    path.write_text(
        f"CLAVIGER_ENV={environment}\n",
        encoding="utf-8",
    )


def test_local_selector_loads_development_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Load only the explicitly selected local development environment."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "development",
    )

    assert config.get_environment_name(selector_path) == "development"
    assert config.get_discord_token(selector_path) == "test-token"
    assert config.get_discord_bot_user_id(selector_path) == 456
    assert config.get_discord_guild_id(selector_path) == 123
    assert config.get_database_path(selector_path) == "data/test.db"


def test_local_selector_rejects_additional_configuration(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Keep the local .env file restricted to environment selection."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"

    selector_path.write_text(
        "\n".join(
            (
                "CLAVIGER_ENV=development",
                "DISCORD_TOKEN=should-not-be-here",
                "",
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        RuntimeError,
        match="must contain only CLAVIGER_ENV",
    ):
        config.get_discord_token(
            selector_path,
        )


def test_missing_local_environment_file_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Fail when the selected local configuration file does not exist."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"

    _write_selector(
        selector_path,
        "development",
    )

    with pytest.raises(
        RuntimeError,
        match="Configuration file",
    ):
        config.get_discord_token(
            selector_path,
        )


def test_environment_file_must_match_selected_environment(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Reject a production file accidentally used as development config."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "production",
    )

    with pytest.raises(
        RuntimeError,
        match="declares CLAVIGER_ENV=production",
    ):
        config.get_discord_token(
            selector_path,
        )


def test_unsupported_environment_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Reject environment names outside the supported set."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"

    _write_selector(
        selector_path,
        "staging",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported CLAVIGER_ENV",
    ):
        config.get_environment_name(
            selector_path,
        )


def test_runtime_environment_can_be_supplied_without_files(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Support container configuration entirely through environment variables."""

    monkeypatch.setenv(
        "CLAVIGER_ENV",
        "production",
    )
    monkeypatch.setenv(
        "DISCORD_TOKEN",
        "runtime-token",
    )
    monkeypatch.setenv(
        "DISCORD_BOT_USER_ID",
        "654",
    )
    monkeypatch.setenv(
        "DISCORD_GUILD_ID",
        "321",
    )
    monkeypatch.setenv(
        "DATABASE_PATH",
        "/data/claviger.db",
    )

    selector_path = tmp_path / ".env"

    assert config.get_environment_name(selector_path) == "production"
    assert config.get_discord_token(selector_path) == "runtime-token"
    assert config.get_discord_bot_user_id(selector_path) == 654
    assert config.get_discord_guild_id(selector_path) == 321
    assert config.get_database_path(selector_path) == "/data/claviger.db"


def test_missing_discord_token_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Fail explicitly when the selected environment has no Discord token."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "development",
        token="",
    )

    with pytest.raises(
        RuntimeError,
        match="DISCORD_TOKEN is missing",
    ):
        config.get_discord_token(
            selector_path,
        )


def test_missing_database_path_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Never silently fall back to an implicit runtime database."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "development",
        database_path="",
    )

    with pytest.raises(
        RuntimeError,
        match="DATABASE_PATH is missing",
    ):
        config.get_database_path(
            selector_path,
        )


def test_invalid_discord_guild_id_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Reject malformed historical fallback guild identifiers before startup."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "development",
        guild_id="not-an-id",
    )

    with pytest.raises(
        RuntimeError,
        match="DISCORD_GUILD_ID must be a valid integer",
    ):
        config.get_discord_guild_id(
            selector_path,
        )


def test_invalid_discord_bot_user_id_is_rejected(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Reject malformed Discord bot identities before startup."""

    monkeypatch.delenv(
        "CLAVIGER_ENV",
        raising=False,
    )

    selector_path = tmp_path / ".env"
    development_path = tmp_path / ".env.development"

    _write_selector(
        selector_path,
        "development",
    )

    _write_environment_file(
        development_path,
        "development",
        bot_user_id="not-an-id",
    )

    with pytest.raises(
        RuntimeError,
        match="DISCORD_BOT_USER_ID must be a valid integer",
    ):
        config.get_discord_bot_user_id(
            selector_path,
        )
