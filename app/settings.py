"""Environment configuration. Everything the bot needs comes from env vars —
there is no admin UI and no secrets table."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"FATAL: {name} is not set", file=sys.stderr)
        sys.exit(1)
    return value


TELEGRAM_BOT_TOKEN: str = _required("TELEGRAM_BOT_TOKEN")

BERLIN_WOHNEN_USERNAME: str = _required("BERLIN_WOHNEN_USERNAME")
BERLIN_WOHNEN_PASSWORD: str = _required("BERLIN_WOHNEN_PASSWORD")

SCRAPE_INTERVAL_SECONDS: int = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "60"))

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH: Path = DATA_DIR / "wohnwatch.sqlite"

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# Listings older than this are pruned by a daily job so the volume stays bounded.
FLAT_RETENTION_DAYS: int = int(os.environ.get("FLAT_RETENTION_DAYS", "30"))
