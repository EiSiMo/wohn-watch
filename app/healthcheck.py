"""Container healthcheck without an HTTP server.

Exit 0 while the scrape loop is producing results, non-zero once it has gone
quiet for long enough that something is genuinely stuck.
"""
import sqlite3
import sys
from datetime import datetime, timezone

from app.settings import DB_PATH, SCRAPE_INTERVAL_SECONDS

# The scraper backs off up to 30 minutes on repeated failures, so the window
# has to clear that — otherwise transient site trouble reads as a dead bot.
MAX_AGE_SECONDS = max(3 * SCRAPE_INTERVAL_SECONDS, 2400)


def main() -> int:
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'last_scrape_at'"
        ).fetchone()
    except sqlite3.Error as e:
        print(f"db unreadable: {e}")
        return 1

    if not row or not row[0]:
        print("no successful scrape yet")
        return 1

    age = (datetime.now(timezone.utc) - datetime.fromisoformat(row[0])).total_seconds()
    if age > MAX_AGE_SECONDS:
        print(f"last scrape {age:.0f}s ago (limit {MAX_AGE_SECONDS}s)")
        return 1

    print(f"ok, last scrape {age:.0f}s ago")
    return 0


if __name__ == "__main__":
    sys.exit(main())
