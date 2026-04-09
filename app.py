from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

from config.logging_config import setup_logging
from config.settings import app_config
from service.main_service import main

setup_logging(app_config.log_level)

if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
