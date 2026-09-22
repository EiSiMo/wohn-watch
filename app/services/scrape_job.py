"""The scrape loop, running as a JobQueue job inside the bot's event loop.

Scrape (in a worker thread, it's synchronous requests) -> upsert -> fan out to
every active chat whose filter matches. One chat's failure never aborts the rest.
"""
import asyncio
import logging
import time

from telegram.error import BadRequest, Forbidden, NetworkError, TimedOut
from telegram.ext import ContextTypes

from app import db, settings, texts
from app.flat import Flat
from app.matching import flat_filter_failures
from app.scraper import Scraper
from app.services import notify

logger = logging.getLogger("wohnwatch.scrape")

# A single chat can't be allowed to eat the whole tick.
MAX_PER_CHAT_PER_TICK = 10

_BACKOFF_CAP = 1800  # 30 minutes


class _Backoff:
    """Exponential backoff for scrape failures. Users never see these —
    a broken login is our problem, not theirs."""

    def __init__(self, base: int):
        self.base = base
        self.failures = 0
        self.until = 0.0

    def active(self) -> bool:
        return time.monotonic() < self.until

    def fail(self) -> int:
        self.failures += 1
        delay = min(self.base * (2 ** (self.failures - 1)), _BACKOFF_CAP)
        self.until = time.monotonic() + delay
        return delay

    def reset(self) -> None:
        self.failures = 0
        self.until = 0.0


_backoff = _Backoff(settings.SCRAPE_INTERVAL_SECONDS)
_scraper = Scraper(settings.BERLIN_WOHNEN_USERNAME, settings.BERLIN_WOHNEN_PASSWORD)
_tick_lock = asyncio.Lock()


async def scrape_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    if _tick_lock.locked():
        logger.warning("previous tick still running — skipping this one")
        return
    async with _tick_lock:
        started = time.monotonic()
        await _scrape_tick(context)
        elapsed = time.monotonic() - started
        if elapsed > settings.SCRAPE_INTERVAL_SECONDS / 2:
            logger.warning("tick took %.1fs of a %ss interval",
                           elapsed, settings.SCRAPE_INTERVAL_SECONDS)


async def _scrape_tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    if _backoff.active():
        return

    raw = await asyncio.to_thread(_scraper.fetch)
    if raw is None:
        delay = _backoff.fail()
        n = db.incr_meta("login_failures")
        logger.warning("scrape failed (%d in a row), retrying in %ds", n, delay)
        return

    _backoff.reset()
    db.set_meta("last_scrape_at", db.now_iso())
    db.set_meta("login_failures", "0")

    new_flats = []
    for data in raw:
        payload = Flat(data).to_payload()
        if db.upsert_flat(payload):
            # Re-read so everyone works off the authoritative discovered_at.
            flat = db.get_flat(payload["id"])
            if flat:
                new_flats.append(flat)

    if db.get_meta("bootstrap_done") != "1":
        db.set_meta("bootstrap_done", "1")
        logger.info("bootstrap seeded %d flats — no notifications sent", len(new_flats))
        return

    if not new_flats:
        return
    logger.info("%d new flats", len(new_flats))

    for chat in db.list_notifiable_chats():
        try:
            await _notify_chat(context.bot, chat, new_flats)
        except Exception:
            logger.exception("notify failed for chat=%s", chat["chat_id"])


async def _notify_chat(bot, chat: dict, new_flats: list[dict]) -> None:
    chat_id = chat["chat_id"]
    f = db.get_filter(chat_id)
    matches = [
        fl for fl in new_flats
        if fl["discovered_at"] > chat["notify_since"]
        and not flat_filter_failures(fl, f)
        and not db.already_notified(chat_id, fl["id"])
    ]
    if not matches:
        return

    for fl in matches[:MAX_PER_CHAT_PER_TICK]:
        try:
            await notify.send_match(bot, chat_id, fl)
            db.mark_notified(chat_id, fl["id"], ok=True)
        except Forbidden:
            # Blocked, deleted, or kicked — this chat will never work again.
            logger.info("chat %s blocked the bot — deleting", chat_id)
            db.delete_chat(chat_id)
            return
        except BadRequest as e:
            if "chat not found" in str(e).lower():
                db.delete_chat(chat_id)
                return
            logger.warning("send failed for chat=%s flat=%s: %s", chat_id, fl["id"], e)
            db.mark_notified(chat_id, fl["id"], ok=False)
        except (TimedOut, NetworkError) as e:
            # Deliberately not retried: a flat alert five minutes late is
            # worthless, and the row stops us trying again next tick.
            logger.warning("send timed out for chat=%s: %s", chat_id, e)
            db.mark_notified(chat_id, fl["id"], ok=False)

    overflow = len(matches) - MAX_PER_CHAT_PER_TICK
    if overflow > 0:
        try:
            await bot.send_message(chat_id, texts.OVERFLOW.format(n=overflow),
                                   parse_mode="Markdown")
        except Exception:
            logger.info("overflow notice failed for chat=%s", chat_id)


async def prune_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    removed = db.prune_flats(settings.FLAT_RETENTION_DAYS)
    if removed:
        logger.info("pruned %d flats older than %d days",
                    removed, settings.FLAT_RETENTION_DAYS)
    dupes = db.duplicate_source_ids()
    if dupes:
        # See the "flats.id is the listing URL" risk — if this ever fires,
        # the same flat is reachable under more than one URL.
        logger.warning("%d source_ids map to multiple listing URLs", len(dupes))
