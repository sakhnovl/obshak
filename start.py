import asyncio
import os

from dotenv import load_dotenv

from src.main import main

load_dotenv()


def validate_environment():
    required_vars = {
        "BOT_TOKEN": os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN"),
        "MYSQL_HOST": os.getenv("MYSQL_HOST"),
        "MYSQL_USER": os.getenv("MYSQL_USER"),
        "MYSQL_DATABASE": os.getenv("MYSQL_DATABASE"),
    }
    missing = [name for name, value in required_vars.items() if not value]
    if missing:
        missing_list = ", ".join(missing)
        raise ValueError(f"Missing required environment variables: {missing_list}")



def run():
    validate_environment()
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    run()
