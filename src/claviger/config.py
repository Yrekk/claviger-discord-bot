import os

from dotenv import load_dotenv


def get_discord_token() -> str:
    """Load and return the Discord bot token from the environment."""
    load_dotenv()

    token = os.getenv("DISCORD_TOKEN")

    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is missing. "
            "Check that your .env file exists and contains DISCORD_TOKEN."
        )

    return token

def get_discord_guild_id() -> int:
    """Load and return the Discord guild ID from the environment."""
    load_dotenv()

    guild_id = os.getenv("DISCORD_GUILD_ID")

    if not guild_id:
        raise RuntimeError(
            "DISCORD_GUILD_ID is missing. "
            "Check that your .env file contains DISCORD_GUILD_ID."
        )

    return int(guild_id)


def get_test_role_id() -> int:
    """Load and return the Discord role ID used for integration testing."""
    load_dotenv()

    role_id = os.getenv("TEST_ROLE_ID")

    if not role_id:
        raise RuntimeError(
            "TEST_ROLE_ID is missing. "
            "Check that your .env file contains TEST_ROLE_ID."
        )

    return int(role_id)

def get_database_path() -> str:
    """Return Claviger's SQLite database path."""
    return os.getenv(
        "DATABASE_PATH",
        "data/claviger.db",
    )

def get_admin_report_forum_id() -> int | None:
    """Return the bootstrap Discord forum used for administrative reports."""
    value = os.getenv(
        "ADMIN_REPORT_FORUM_ID",
    )

    if value is None or not value.strip():
        return None

    return int(value)