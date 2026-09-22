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


# The only secret this bot has. inberlinwohnen.de is scraped without an
# account — the public Wohnungsfinder carries the same listings and fields.
TELEGRAM_BOT_TOKEN: str = _required("TELEGRAM_BOT_TOKEN")

SCRAPE_INTERVAL_SECONDS: int = int(os.environ.get("SCRAPE_INTERVAL_SECONDS", "60"))

DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH: Path = DATA_DIR / "wohnwatch.sqlite"

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").upper()

# Listings older than this are pruned by a daily job so the volume stays bounded.
FLAT_RETENTION_DAYS: int = int(os.environ.get("FLAT_RETENTION_DAYS", "30"))

# The usage log keeps message-level detail, so it is pruned too. The anonymous
# lifetime counters in `meta` are never pruned.
EVENT_RETENTION_DAYS: int = int(os.environ.get("EVENT_RETENTION_DAYS", "90"))
