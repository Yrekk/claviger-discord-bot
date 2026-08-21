import pytest

from claviger import config


def test_get_discord_token_returns_environment_token(monkeypatch) -> None:
    """Return the Discord token when it exists in the environment."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")

    token = config.get_discord_token()

    assert token == "test-token"


def test_get_discord_token_raises_when_missing(monkeypatch) -> None:
    """Fail explicitly when the Discord token is missing."""
    monkeypatch.setattr(config, "load_dotenv", lambda: None)
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="DISCORD_TOKEN is missing"):
        config.get_discord_token()