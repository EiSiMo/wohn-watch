"""SQLite data layer.

Three concerns: one row per Telegram chat with its filter, a global flats
table that doubles as the dedup gate, and a per-chat delivery log.

Connection handling is lifted from lazyflat's web/db.py: WAL, one connection
per thread via threading.local, and a module-level write lock. The bot runs
everything in one process (the scraper via asyncio.to_thread), so that lock
genuinely serializes every writer.
"""
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from app.providers import UNKNOWN
from app.settings import DB_PATH

logger = logging.getLogger("wohnwatch.db")

_lock = threading.Lock()
_local = threading.local()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")  # required for the /stop cascade
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _get_conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        c = _connect()
        _local.conn = c
    return c


@contextmanager
def _tx():
    """Atomic BEGIN IMMEDIATE … COMMIT/ROLLBACK. Needed for multi-statement
    writes because connections run in autocommit mode (isolation_level=None)."""
    c = _get_conn()
    c.execute("BEGIN IMMEDIATE")
    try:
        yield c
    except Exception:
        c.execute("ROLLBACK")
        raise
    else:
        c.execute("COMMIT")


def now_iso() -> str:
    """Microsecond precision on purpose: discovered_at and notify_since are
    compared with a strict `>`, so a coarser clock would make a flat found in
    the same second a chat activated look like backlog (or vice versa)."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _row(r) -> dict | None:
    return None if r is None else {k: r[k] for k in r.keys()}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    chat_id      INTEGER PRIMARY KEY,
    state        TEXT NOT NULL DEFAULT 'new',
    setup_step   TEXT NOT NULL DEFAULT '',
    awaiting     TEXT NOT NULL DEFAULT '',
    menu_msg_id  INTEGER,
    notify_since TEXT,
    language     TEXT NOT NULL DEFAULT 'de',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_filters (
    chat_id      INTEGER PRIMARY KEY REFERENCES chats(chat_id) ON DELETE CASCADE,
    rooms_min    REAL,
    rooms_max    REAL,
    max_rent     REAL,
    min_size     REAL,
    wbs_required TEXT NOT NULL DEFAULT '',
    districts    TEXT NOT NULL DEFAULT '',
    providers    TEXT NOT NULL DEFAULT '',
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flats (
    id                 TEXT PRIMARY KEY,
    source_id          TEXT NOT NULL DEFAULT '',
    link               TEXT NOT NULL,
    provider           TEXT NOT NULL DEFAULT 'unbekannt',
    address            TEXT NOT NULL DEFAULT '',
    district           TEXT,
    rooms              REAL,
    size               REAL,
    total_rent         REAL,
    sqm_price          REAL,
    wbs                TEXT NOT NULL DEFAULT '',
    address_link_gmaps TEXT NOT NULL DEFAULT '',
    payload_json       TEXT NOT NULL,
    discovered_at      TEXT NOT NULL,
    last_seen_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_flats_discovered ON flats(discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_flats_source ON flats(source_id);

CREATE TABLE IF NOT EXISTS notifications (
    chat_id INTEGER NOT NULL REFERENCES chats(chat_id) ON DELETE CASCADE,
    flat_id TEXT    NOT NULL REFERENCES flats(id)     ON DELETE CASCADE,
    sent_at TEXT    NOT NULL,
    ok      INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (chat_id, flat_id)
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts        TEXT    NOT NULL,
    chat_id   INTEGER REFERENCES chats(chat_id) ON DELETE CASCADE,
    direction TEXT    NOT NULL,          -- 'in' | 'out' | 'sys'
    kind      TEXT    NOT NULL,          -- command | text | callback | match | reply | ...
    detail    TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_chat ON events(chat_id);
"""


def init_db() -> None:
    with _lock:
        _get_conn().executescript(SCHEMA)
    logger.info("DB initialized")


# ---------------------------------------------------------------------------
# Chats
# ---------------------------------------------------------------------------

_CHAT_FIELDS = {"state", "setup_step", "awaiting", "menu_msg_id", "notify_since", "language"}


def ensure_chat(chat_id: int, language: str | None = None) -> dict:
    """Create the chat and its filter row if they don't exist yet. Idempotent.

    `language` only takes effect on first creation (resolved from Telegram's
    language_code by the caller) — it's silently ignored for an existing row,
    same as the column DEFAULT is for every call site that doesn't pass one.
    """
    with _lock, _tx() as c:
        ts = now_iso()
        if language:
            cur = c.execute(
                "INSERT OR IGNORE INTO chats(chat_id, language, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (chat_id, language, ts, ts),
            )
        else:
            cur = c.execute(
                "INSERT OR IGNORE INTO chats(chat_id, created_at, updated_at) VALUES (?, ?, ?)",
                (chat_id, ts, ts),
            )
        created = cur.rowcount == 1
        c.execute(
            "INSERT OR IGNORE INTO chat_filters(chat_id, updated_at) VALUES (?, ?)",
            (chat_id, ts),
        )
    if created:
        incr_meta("chats_created_total")
        log_event(chat_id, "sys", "chat_created")
    return get_chat(chat_id)


def get_chat(chat_id: int) -> dict | None:
    return _row(
        _get_conn().execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
    )


def set_chat(chat_id: int, **fields) -> None:
    data = {k: v for k, v in fields.items() if k in _CHAT_FIELDS}
    if not data:
        return
    cols = ", ".join(f"{k} = ?" for k in data)
    with _lock:
        _get_conn().execute(
            f"UPDATE chats SET {cols}, updated_at = ? WHERE chat_id = ?",
            (*data.values(), now_iso(), chat_id),
        )


def delete_chat(chat_id: int) -> None:
    """Hard delete — cascades chat_filters, notifications and events.

    The per-chat log goes with it, which is what /hilfe promises. The lifetime
    counters in `meta` are anonymous totals and deliberately survive, so usage
    statistics don't get rewritten by a single deletion.
    """
    with _lock:
        cur = _get_conn().execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    if cur.rowcount:
        incr_meta("chats_deleted_total")


def list_notifiable_chats() -> list[dict]:
    rows = _get_conn().execute(
        "SELECT * FROM chats WHERE state = 'active' AND notify_since IS NOT NULL"
    ).fetchall()
    return [_row(r) for r in rows]


def count_chats() -> int:
    return int(_get_conn().execute("SELECT COUNT(*) AS n FROM chats").fetchone()["n"])


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

FILTER_FIELDS = (
    "rooms_min", "rooms_max", "max_rent", "min_size",
    "wbs_required", "districts", "providers",
)


def get_filter(chat_id: int) -> dict:
    row = _get_conn().execute(
        "SELECT * FROM chat_filters WHERE chat_id = ?", (chat_id,)
    ).fetchone()
    return _row(row) or {}


def update_filter(chat_id: int, data: dict) -> None:
    """Explicit None clears a numeric field (= no limit), so this uses
    `k in data` rather than iterating truthy values."""
    cols = [k for k in FILTER_FIELDS if k in data]
    if not cols:
        return
    assignments = ", ".join(f"{k} = ?" for k in cols)
    with _lock:
        _get_conn().execute(
            f"UPDATE chat_filters SET {assignments}, updated_at = ? WHERE chat_id = ?",
            (*(data[k] for k in cols), now_iso(), chat_id),
        )


def clear_filter(chat_id: int) -> None:
    update_filter(chat_id, {
        "rooms_min": None, "rooms_max": None, "max_rent": None, "min_size": None,
        "wbs_required": "", "districts": "", "providers": "",
    })


# ---------------------------------------------------------------------------
# Flats
# ---------------------------------------------------------------------------

_FLAT_COLS = (
    "id", "source_id", "link", "provider", "address", "district", "rooms",
    "size", "total_rent", "sqm_price", "wbs", "address_link_gmaps", "payload_json",
)


def _flat_values(payload: dict) -> list:
    """Bind values for _FLAT_COLS, coercing the NOT NULL text columns.

    This matters more than it looks: INSERT OR IGNORE silently swallows a
    NOT NULL violation, which would make upsert_flat answer False forever
    for a flat that was never stored.
    """
    return [
        str(payload["id"]),
        str(payload.get("source_id") or ""),
        str(payload.get("link") or ""),
        str(payload.get("provider") or UNKNOWN),
        str(payload.get("address") or ""),
        payload.get("district"),           # nullable: unknown PLZ
        payload.get("rooms"),
        payload.get("size"),
        payload.get("total_rent"),
        payload.get("sqm_price"),
        str(payload.get("wbs") or ""),
        str(payload.get("address_link_gmaps") or ""),
        str(payload.get("payload_json") or "{}"),
    ]


def upsert_flat(payload: dict) -> bool:
    """Insert a flat. Returns True **only** when it was newly inserted.

    This return value is the entire dedup gate — every scrape re-posts the
    full listing page, so anything that already exists must answer False.
    INSERT OR IGNORE + rowcount is atomic, so two concurrent callers can
    never both see True for the same id.
    """
    flat_id = str(payload["id"])
    ts = now_iso()
    placeholders = ", ".join("?" * (len(_FLAT_COLS) + 2))
    with _lock:
        cur = _get_conn().execute(
            f"INSERT OR IGNORE INTO flats({', '.join(_FLAT_COLS)}, discovered_at, last_seen_at) "
            f"VALUES ({placeholders})",
            (*_flat_values(payload), ts, ts),
        )
        if cur.rowcount == 1:
            return True
        cur = _get_conn().execute(
            "UPDATE flats SET last_seen_at = ? WHERE id = ?", (ts, flat_id)
        )
        if cur.rowcount == 0:
            # Neither inserted nor present — OR IGNORE ate a constraint error.
            logger.error("flat %s was neither inserted nor found; payload rejected", flat_id)
        return False


def get_flat(flat_id: str) -> dict | None:
    return _row(
        _get_conn().execute("SELECT * FROM flats WHERE id = ?", (flat_id,)).fetchone()
    )


def count_flats() -> int:
    return int(_get_conn().execute("SELECT COUNT(*) AS n FROM flats").fetchone()["n"])


def prune_flats(older_than_days: int) -> int:
    """Delete stale listings so the volume stays bounded. Cascades notifications."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat(
        timespec="microseconds"
    )
    with _lock:
        cur = _get_conn().execute("DELETE FROM flats WHERE discovered_at < ?", (cutoff,))
        return cur.rowcount


def duplicate_source_ids() -> list[dict]:
    """Diagnostic for the "flats.id is the URL" risk: the same listing showing
    up under more than one URL. Should stay empty."""
    rows = _get_conn().execute(
        "SELECT source_id, COUNT(*) AS n FROM flats "
        "WHERE source_id != '' GROUP BY source_id HAVING n > 1"
    ).fetchall()
    return [_row(r) for r in rows]


# ---------------------------------------------------------------------------
# Delivery log
# ---------------------------------------------------------------------------

def already_notified(chat_id: int, flat_id: str) -> bool:
    return _get_conn().execute(
        "SELECT 1 FROM notifications WHERE chat_id = ? AND flat_id = ?",
        (chat_id, flat_id),
    ).fetchone() is not None


def mark_notified(chat_id: int, flat_id: str, ok: bool = True) -> None:
    with _lock:
        _get_conn().execute(
            "INSERT OR REPLACE INTO notifications(chat_id, flat_id, sent_at, ok) "
            "VALUES (?, ?, ?, ?)",
            (chat_id, flat_id, now_iso(), 1 if ok else 0),
        )


def count_notifications(chat_id: int) -> int:
    return int(_get_conn().execute(
        "SELECT COUNT(*) AS n FROM notifications WHERE chat_id = ? AND ok = 1",
        (chat_id,),
    ).fetchone()["n"])


# ---------------------------------------------------------------------------
# Usage log
# ---------------------------------------------------------------------------

MAX_DETAIL_CHARS = 300


def log_event(chat_id: int | None, direction: str, kind: str, detail: str = "") -> None:
    """Record one interaction. Best-effort: logging must never break a reply."""
    try:
        with _lock:
            _get_conn().execute(
                "INSERT INTO events(ts, chat_id, direction, kind, detail) VALUES (?, ?, ?, ?, ?)",
                (now_iso(), chat_id, direction, kind, (detail or "")[:MAX_DETAIL_CHARS]),
            )
        incr_meta(f"ev_{direction}_{kind}")
    except Exception:
        logger.exception("failed to log event %s/%s", direction, kind)


def recent_events(limit: int = 50, chat_id: int | None = None) -> list[dict]:
    sql = "SELECT * FROM events"
    args: list = []
    if chat_id is not None:
        sql += " WHERE chat_id = ?"
        args.append(chat_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    return [_row(r) for r in _get_conn().execute(sql, args).fetchall()]


def events_per_day(days: int = 14) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(
        timespec="microseconds"
    )
    rows = _get_conn().execute(
        "SELECT substr(ts, 1, 10) AS day, direction, kind, COUNT(*) AS n "
        "FROM events WHERE ts >= ? GROUP BY day, direction, kind ORDER BY day DESC",
        (cutoff,),
    ).fetchall()
    return [_row(r) for r in rows]


def command_counts(limit: int = 15) -> list[dict]:
    rows = _get_conn().execute(
        "SELECT detail AS command, COUNT(*) AS n FROM events "
        "WHERE direction = 'in' AND kind = 'command' "
        "GROUP BY detail ORDER BY n DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row(r) for r in rows]


def chat_activity(limit: int = 20) -> list[dict]:
    rows = _get_conn().execute(
        "SELECT c.chat_id, c.state, c.created_at, "
        "       (SELECT COUNT(*) FROM events e WHERE e.chat_id = c.chat_id AND e.direction = 'in') AS msgs, "
        "       (SELECT COUNT(*) FROM notifications n WHERE n.chat_id = c.chat_id AND n.ok = 1) AS matches, "
        "       (SELECT MAX(ts) FROM events e WHERE e.chat_id = c.chat_id) AS last_seen "
        "FROM chats c ORDER BY last_seen DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row(r) for r in rows]


def prune_events(older_than_days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat(
        timespec="microseconds"
    )
    with _lock:
        cur = _get_conn().execute("DELETE FROM events WHERE ts < ?", (cutoff,))
        return cur.rowcount


def counters() -> dict[str, int]:
    """The lifetime totals that survive chat deletion."""
    rows = _get_conn().execute(
        "SELECT key, value FROM meta WHERE key LIKE 'ev_%' OR key LIKE 'chats_%'"
    ).fetchall()
    out = {}
    for r in rows:
        try:
            out[r["key"]] = int(r["value"])
        except (TypeError, ValueError):
            continue
    return out


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------

def get_meta(key: str, default: str = "") -> str:
    row = _get_conn().execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(key: str, value: str) -> None:
    with _lock:
        _get_conn().execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )


def incr_meta(key: str) -> int:
    with _lock, _tx() as c:
        row = c.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        try:
            n = int(row["value"]) + 1 if row else 1
        except (TypeError, ValueError):
            n = 1
        c.execute(
            "INSERT INTO meta(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(n)),
        )
        return n
