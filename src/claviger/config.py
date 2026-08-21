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