from claviger.bot import ClavigerBot
from claviger.config import get_discord_token


def main() -> None:
    token = get_discord_token()

    bot = ClavigerBot()
    bot.run(token)


if __name__ == "__main__":
    main()
