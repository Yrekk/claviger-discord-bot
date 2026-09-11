import logging

from claviger.bot import ClavigerBot
from claviger.config import get_discord_token
from claviger.models.runtime_restart_model import RuntimeRestartRequest

logger = logging.getLogger(__name__)


def main() -> None:
    token = get_discord_token()

    restart_request: RuntimeRestartRequest | None = None

    while True:
        bot = ClavigerBot(
            startup_restart_request=restart_request,
        )

        bot.run(
            token,
        )

        if not bot.restart_requested:
            break

        restart_request = bot.pending_restart_request

        if restart_request is None:
            raise RuntimeError("Runtime restart was requested without restart context.")

        logger.info("Instance courante fermée. Relance de l'application...")


if __name__ == "__main__":
    main()
