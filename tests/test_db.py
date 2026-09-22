import concurrent.futures
import itertools

import pytest

from app import db

_ids = itertools.count(1)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    db.init_db()


def _chat_id() -> int:
    return 900_000 + next(_ids)


def _payload(flat_id: str) -> dict:
    return {
        "id": flat_id, "source_id": "1", "link": flat_id, "provider": "wbm.de",
        "address": "Teststr. 1, 10115, Mitte", "district": "Mitte",
        "rooms": 2.0, "size": 50.0, "total_rent": 900.0, "sqm_price": 18.0,
        "wbs": "", "address_link_gmaps": "https://maps", "payload_json": "{}",
    }


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()


def test_upsert_is_true_only_on_first_insert():
    flat_id = f"https://example.test/{next(_ids)}"
    assert db.upsert_flat(_payload(flat_id)) is True
    assert db.upsert_flat(_payload(flat_id)) is False
    assert db.get_flat(flat_id)["address"] == "Teststr. 1, 10115, Mitte"


def test_upsert_touches_last_seen_without_moving_discovered_at():
    flat_id = f"https://example.test/{next(_ids)}"
    db.upsert_flat(_payload(flat_id))
    first = db.get_flat(flat_id)
    db.upsert_flat(_payload(flat_id))
    again = db.get_flat(flat_id)
    assert again["discovered_at"] == first["discovered_at"]


def test_upsert_rejects_nothing_silently():
    """INSERT OR IGNORE would swallow a NOT NULL violation — a payload with
    None in every text column must still land in the table."""
    flat_id = f"https://example.test/{next(_ids)}"
    sparse = {"id": flat_id, "link": None, "provider": None, "address": None,
              "wbs": None, "address_link_gmaps": None, "payload_json": None}
    assert db.upsert_flat(sparse) is True
    assert db.get_flat(flat_id) is not None


def test_concurrent_upsert_yields_exactly_one_true():
    flat_id = f"https://example.test/{next(_ids)}"
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: db.upsert_flat(_payload(flat_id)), range(4)))
    assert sum(results) == 1


def test_ensure_chat_is_idempotent_and_creates_the_filter_row():
    chat_id = _chat_id()
    first = db.ensure_chat(chat_id)
    db.ensure_chat(chat_id)
    assert db.get_chat(chat_id)["created_at"] == first["created_at"]
    assert db.get_filter(chat_id)["chat_id"] == chat_id


def test_chat_language_defaults_to_german():
    chat_id = _chat_id()
    db.ensure_chat(chat_id)
    assert db.get_chat(chat_id)["language"] == "de"


def test_ensure_chat_seeds_language_only_on_first_creation():
    chat_id = _chat_id()
    db.ensure_chat(chat_id, language="en")
    assert db.get_chat(chat_id)["language"] == "en"
    db.ensure_chat(chat_id, language="de")  # existing row — must not overwrite
    assert db.get_chat(chat_id)["language"] == "en"


def test_set_chat_can_change_language():
    chat_id = _chat_id()
    db.ensure_chat(chat_id)
    db.set_chat(chat_id, language="en")
    assert db.get_chat(chat_id)["language"] == "en"


def test_update_filter_allows_clearing_with_none():
    chat_id = _chat_id()
    db.ensure_chat(chat_id)
    db.update_filter(chat_id, {"max_rent": 1200.0})
    assert db.get_filter(chat_id)["max_rent"] == 1200.0
    db.update_filter(chat_id, {"max_rent": None})
    assert db.get_filter(chat_id)["max_rent"] is None


def test_update_filter_ignores_unknown_columns():
    chat_id = _chat_id()
    db.ensure_chat(chat_id)
    db.update_filter(chat_id, {"rooms_min": 2.0, "evil": "DROP TABLE chats"})
    assert db.get_filter(chat_id)["rooms_min"] == 2.0


def test_set_chat_ignores_unknown_columns():
    chat_id = _chat_id()
    db.ensure_chat(chat_id)
    db.set_chat(chat_id, state="active", nonsense="x")
    assert db.get_chat(chat_id)["state"] == "active"


def test_delete_chat_leaves_no_orphans():
    chat_id = _chat_id()
    flat_id = f"https://example.test/{next(_ids)}"
    db.ensure_chat(chat_id)
    db.upsert_flat(_payload(flat_id))
    db.mark_notified(chat_id, flat_id)
    assert db.already_notified(chat_id, flat_id)

    db.delete_chat(chat_id)

    assert db.get_chat(chat_id) is None
    assert db.get_filter(chat_id) == {}
    assert db.already_notified(chat_id, flat_id) is False


def test_only_active_chats_with_a_watermark_are_notifiable():
    active, paused, no_watermark = _chat_id(), _chat_id(), _chat_id()
    for c in (active, paused, no_watermark):
        db.ensure_chat(c)
    db.set_chat(active, state="active", notify_since=db.now_iso())
    db.set_chat(paused, state="paused", notify_since=db.now_iso())
    db.set_chat(no_watermark, state="active")

    ids = {c["chat_id"] for c in db.list_notifiable_chats()}
    assert active in ids
    assert paused not in ids and no_watermark not in ids


def test_notifications_are_counted_only_when_delivered():
    chat_id = _chat_id()
    ok_flat = f"https://example.test/{next(_ids)}"
    bad_flat = f"https://example.test/{next(_ids)}"
    db.ensure_chat(chat_id)
    db.upsert_flat(_payload(ok_flat))
    db.upsert_flat(_payload(bad_flat))
    db.mark_notified(chat_id, ok_flat, ok=True)
    db.mark_notified(chat_id, bad_flat, ok=False)

    assert db.count_notifications(chat_id) == 1
    # Both rows still block a retry next tick.
    assert db.already_notified(chat_id, bad_flat)


def test_meta_roundtrip_and_counter():
    db.set_meta("probe", "1")
    assert db.get_meta("probe") == "1"
    assert db.get_meta("missing", "fallback") == "fallback"
    db.set_meta("counter", "0")
    assert db.incr_meta("counter") == 1
    assert db.incr_meta("counter") == 2
