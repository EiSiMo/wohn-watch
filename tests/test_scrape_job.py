"""End-to-end test of scrape -> dedup -> fan-out, with a stub bot and a stub
scraper. No network, no Telegram token."""
import asyncio
import itertools
import types

import pytest
from telegram.error import Forbidden

from app import db
from app.services import scrape_job

_ids = itertools.count(1)


class FakeBot:
    def __init__(self, raises=None):
        self.sent: list[tuple[int, str]] = []
        self.raises = raises

    async def send_message(self, chat_id, text, **kwargs):
        if self.raises:
            raise self.raises
        self.sent.append((chat_id, text))


def _ctx(bot):
    return types.SimpleNamespace(bot=bot)


def _listing(rooms="2", rent="900", plz="10115", host="gewobag.de"):
    n = next(_ids)
    return {
        "id": str(n),
        "link": f"https://www.{host}/angebot/{n}",
        "Adresse": f"Teststr. {n}, {plz}, Mitte",
        "Zimmeranzahl": rooms,
        "Wohnfläche": "60",
        "Gesamtmiete": rent,
        "WBS": "nicht erforderlich",
    }


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets its own database file and its own bootstrap state."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.sqlite")
    if hasattr(db._local, "conn"):
        db._local.conn.close()
        del db._local.conn
    db.init_db()
    scrape_job._backoff.reset()
    yield
    if hasattr(db._local, "conn"):
        db._local.conn.close()
        del db._local.conn


def _run(listings, bot, monkeypatch):
    """Drive one tick against a stubbed scraper. `listings is None` simulates a
    transient failure."""
    monkeypatch.setattr(scrape_job._scraper, "fetch", lambda: listings)
    asyncio.run(scrape_job._scrape_tick(_ctx(bot)))


def _active_chat(filters=None) -> int:
    chat_id = 1000 + next(_ids)
    db.ensure_chat(chat_id)
    if filters:
        db.update_filter(chat_id, filters)
    db.set_chat(chat_id, state="active", notify_since=db.now_iso())
    return chat_id


# -- bootstrap --------------------------------------------------------------

def test_first_run_seeds_without_notifying(monkeypatch):
    _active_chat()
    bot = FakeBot()
    _run([_listing(), _listing(), _listing()], bot, monkeypatch)

    assert db.count_flats() == 3
    assert db.get_meta("bootstrap_done") == "1"
    assert bot.sent == []


def test_second_run_notifies(monkeypatch):
    chat_id = _active_chat()
    bot = FakeBot()
    _run([_listing()], bot, monkeypatch)      # bootstrap
    _run([_listing()], bot, monkeypatch)      # one genuinely new listing

    assert [c for c, _ in bot.sent] == [chat_id]
    assert "Teststr." in bot.sent[0][1]


# -- dedup and filters ------------------------------------------------------

def test_unchanged_listings_are_not_resent(monkeypatch):
    _active_chat()
    bot = FakeBot()
    _run([], bot, monkeypatch)
    fresh = _listing()
    _run([fresh], bot, monkeypatch)
    _run([fresh], bot, monkeypatch)
    _run([fresh], bot, monkeypatch)

    assert len(bot.sent) == 1


def test_filter_excludes_non_matching_flats(monkeypatch):
    _active_chat({"max_rent": 800.0})
    bot = FakeBot()
    _run([], bot, monkeypatch)
    _run([_listing(rent="1500")], bot, monkeypatch)

    assert bot.sent == []


def test_provider_filter(monkeypatch):
    _active_chat({"providers": "wbm.de"})
    bot = FakeBot()
    _run([], bot, monkeypatch)
    _run([_listing(host="gewobag.de")], bot, monkeypatch)
    assert bot.sent == []
    _run([_listing(host="wbm.de")], bot, monkeypatch)
    assert len(bot.sent) == 1


def test_paused_chat_gets_nothing(monkeypatch):
    chat_id = _active_chat()
    db.set_chat(chat_id, state="paused")
    bot = FakeBot()
    _run([], bot, monkeypatch)
    _run([_listing()], bot, monkeypatch)

    assert bot.sent == []


# -- cold start -------------------------------------------------------------

def test_chat_activated_after_a_flat_was_found_does_not_get_it(monkeypatch):
    bot = FakeBot()
    _run([], bot, monkeypatch)
    _run([_listing()], bot, monkeypatch)       # found before anyone signed up

    late = _active_chat()                      # notify_since = now
    _run([], bot, monkeypatch)                 # nothing new
    assert bot.sent == []

    _run([_listing()], bot, monkeypatch)       # a genuinely new one
    assert [c for c, _ in bot.sent] == [late]


# -- robustness -------------------------------------------------------------

def test_blocked_chat_is_deleted(monkeypatch):
    chat_id = _active_chat()
    bot = FakeBot(raises=Forbidden("bot was blocked by the user"))
    _run([], bot, monkeypatch)
    _run([_listing()], bot, monkeypatch)

    assert db.get_chat(chat_id) is None


def test_one_broken_chat_does_not_stop_the_others(monkeypatch):
    good = _active_chat()
    bad = _active_chat()

    class PickyBot(FakeBot):
        async def send_message(self, chat_id, text, **kwargs):
            if chat_id == bad:
                raise RuntimeError("boom")
            self.sent.append((chat_id, text))

    bot = PickyBot()
    _run([], bot, monkeypatch)
    _run([_listing()], bot, monkeypatch)

    assert [c for c, _ in bot.sent] == [good]


def test_scrape_failure_backs_off_and_sends_nothing(monkeypatch):
    _active_chat()
    bot = FakeBot()
    _run([], bot, monkeypatch)
    before = db.get_meta("last_scrape_at")

    _run(None, bot, monkeypatch)               # None = transient failure

    assert bot.sent == []
    assert db.get_meta("last_scrape_at") == before
    assert db.get_meta("scrape_failures") == "1"
    assert scrape_job._backoff.active()

    # While backed off, a tick must not even hit the scraper.
    _run([_listing()], bot, monkeypatch)
    assert bot.sent == []


def test_overflow_notice_caps_a_single_tick(monkeypatch):
    _active_chat()
    bot = FakeBot()
    _run([], bot, monkeypatch)
    _run([_listing() for _ in range(scrape_job.MAX_PER_CHAT_PER_TICK + 3)],
         bot, monkeypatch)

    assert len(bot.sent) == scrape_job.MAX_PER_CHAT_PER_TICK + 1
    assert "3" in bot.sent[-1][1]
