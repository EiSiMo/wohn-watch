"""The usage log: every incoming update is recorded, and /stop really removes
a chat's entries while the anonymous totals survive."""
import asyncio
import itertools
import types

import pytest

from app import db
from app.handlers import tracking

_ids = itertools.count(1)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.sqlite")
    if hasattr(db._local, "conn"):
        db._local.conn.close()
        del db._local.conn
    db.init_db()
    yield
    if hasattr(db._local, "conn"):
        db._local.conn.close()
        del db._local.conn


def _update(chat_id, *, text=None, data=None, media=None):
    msg = None
    if text is not None or media is not None:
        msg = types.SimpleNamespace(text=text)
        for attr in ("photo", "sticker", "document", "voice", "video", "audio",
                     "animation", "location", "contact"):
            setattr(msg, attr, media == attr or None)
    cq = types.SimpleNamespace(data=data) if data is not None else None
    return types.SimpleNamespace(
        callback_query=cq,
        effective_message=msg,
        effective_chat=types.SimpleNamespace(id=chat_id),
    )


def _track(update):
    asyncio.run(tracking.track(update, types.SimpleNamespace()))


def test_commands_texts_callbacks_and_media_are_all_recorded():
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="/start"))
    _track(_update(chat_id, text="hallo bot"))
    _track(_update(chat_id, data="m:rent"))
    _track(_update(chat_id, media="sticker"))

    kinds = [(e["kind"], e["detail"]) for e in db.recent_events(10, chat_id)]
    assert ("command", "/start") in kinds
    assert ("text", "hallo bot") in kinds
    assert ("callback", "m:rent") in kinds
    assert ("media", "sticker") in kinds


def test_command_detail_strips_arguments_and_bot_suffix():
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="/Filter@wohnwatch_bot 2 Zimmer"))
    assert db.recent_events(1, chat_id)[0]["detail"] == "/filter"


def test_tracking_creates_the_chat_so_events_have_a_parent():
    chat_id = 500 + next(_ids)
    assert db.get_chat(chat_id) is None
    _track(_update(chat_id, text="/start"))
    assert db.get_chat(chat_id) is not None


def test_long_messages_are_truncated():
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="x" * 5000))
    assert len(db.recent_events(1, chat_id)[0]["detail"]) == db.MAX_DETAIL_CHARS


def test_tracking_never_raises_on_a_broken_update():
    _track(types.SimpleNamespace(callback_query=None, effective_message=None,
                                 effective_chat=None))


def test_stop_deletes_the_chats_log_but_keeps_the_totals():
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="/start"))
    _track(_update(chat_id, text="hallo"))
    assert len(db.recent_events(10, chat_id)) >= 2
    before = db.counters()

    db.delete_chat(chat_id)

    assert db.recent_events(10, chat_id) == []
    after = db.counters()
    assert after["ev_in_text"] == before["ev_in_text"]
    assert after["chats_created_total"] == before["chats_created_total"]
    assert after["chats_deleted_total"] == before.get("chats_deleted_total", 0) + 1


def test_counters_track_each_kind():
    chat_id = 500 + next(_ids)
    start = db.counters().get("ev_in_command", 0)
    _track(_update(chat_id, text="/status"))
    _track(_update(chat_id, text="/status"))
    assert db.counters()["ev_in_command"] == start + 2


def test_events_are_pruned_by_age_but_recent_ones_survive():
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="/start"))
    db._get_conn().execute(
        "INSERT INTO events(ts, chat_id, direction, kind, detail) "
        "VALUES ('2020-01-01T00:00:00.000000+00:00', ?, 'in', 'text', 'alt')",
        (chat_id,),
    )
    assert db.prune_events(30) == 1
    details = [e["detail"] for e in db.recent_events(10, chat_id)]
    assert "alt" not in details
    assert "/start" in details


def test_reports_run_on_an_empty_and_a_populated_database():
    from app import stats

    stats.report(days=7, chats=5, tail=5)          # empty
    chat_id = 500 + next(_ids)
    _track(_update(chat_id, text="/start"))
    _track(_update(chat_id, data="w:start"))
    stats.report(days=7, chats=5, tail=5)          # populated

    assert db.command_counts()[0]["command"] == "/start"
    assert db.chat_activity(5)[0]["chat_id"] == chat_id
    assert db.events_per_day(7)
