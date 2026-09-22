"""Drive the button flow with stub Telegram objects, to check that the wizard
state machine and the filter writes actually line up."""
import asyncio
import itertools
import types

import pytest

from app import db, keyboards
from app.handlers import callbacks

_ids = itertools.count(1)


class FakeQuery:
    def __init__(self, data, chat_id, message_id):
        self.data = data
        self.message = types.SimpleNamespace(message_id=message_id)
        self.answers: list[str | None] = []
        self.text: str | None = None
        self.markup = None

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)

    async def edit_message_text(self, text, reply_markup=None, **kwargs):
        self.text = text
        self.markup = reply_markup


class FakeBot:
    def __init__(self):
        self.sent = []
        self.edited = []
        self._next_id = itertools.count(5000)

    async def send_message(self, chat_id, text, reply_markup=None, **kwargs):
        mid = next(self._next_id)
        self.sent.append((chat_id, text, mid))
        return types.SimpleNamespace(message_id=mid)

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kwargs):
        self.edited.append((chat_id, message_id, text))


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


class Session:
    """One chat, remembering which message the menu currently lives in."""

    def __init__(self):
        self.chat_id = 2000 + next(_ids)
        self.bot = FakeBot()
        db.ensure_chat(self.chat_id)
        db.set_chat(self.chat_id, menu_msg_id=1)
        self.menu_msg_id = 1

    def press(self, data: str, message_id: int | None = None) -> FakeQuery:
        q = FakeQuery(data, self.chat_id, message_id or self.menu_msg_id)
        update = types.SimpleNamespace(
            callback_query=q,
            effective_chat=types.SimpleNamespace(id=self.chat_id),
        )
        ctx = types.SimpleNamespace(bot=self.bot)
        asyncio.run(callbacks.route(update, ctx))
        chat = db.get_chat(self.chat_id)
        if chat:
            self.menu_msg_id = chat["menu_msg_id"]
        return q

    @property
    def filter(self) -> dict:
        return db.get_filter(self.chat_id)

    @property
    def chat(self) -> dict:
        return db.get_chat(self.chat_id)


# -- the guided setup -------------------------------------------------------

def test_full_setup_walk_activates_the_chat():
    s = Session()
    s.press("w:start")
    assert s.chat["state"] == "setup"
    assert s.chat["setup_step"] == "rmin"

    s.press("set:rmin:2")
    s.press("w:next")
    assert s.chat["setup_step"] == "rmax"
    s.press("set:rmax:3")
    s.press("w:next")
    s.press("set:rent:1200")
    s.press("w:next")
    s.press("set:size:60")
    s.press("w:next")
    s.press("set:wbs:no")
    s.press("w:next")
    s.press("tog:d:4")            # drop Spandau
    s.press("w:next")
    s.press("tog:p:wbm.de")       # drop WBM
    q = s.press("w:next")         # -> confirmation

    assert s.chat["setup_step"] == "confirm"
    assert "aktivieren" in q.markup.inline_keyboard[0][0].text

    s.press("f:activate")
    chat = s.chat
    assert chat["state"] == "active"
    assert chat["notify_since"] is not None
    assert chat["setup_step"] == ""

    f = s.filter
    assert (f["rooms_min"], f["rooms_max"]) == (2.0, 3.0)
    assert f["max_rent"] == 1200.0 and f["min_size"] == 60.0
    assert f["wbs_required"] == "no"
    assert "Spandau" not in f["districts"] and "Mitte" in f["districts"]
    assert "wbm.de" not in f["providers"] and "gewobag.de" in f["providers"]


def test_skipping_every_step_still_activates_with_an_empty_filter():
    s = Session()
    s.press("w:start")
    for _ in keyboards.WIZARD_SCREENS:
        s.press("w:next")
    s.press("f:activate")

    assert s.chat["state"] == "active"
    assert s.filter["max_rent"] is None
    assert s.filter["districts"] == ""


def test_back_walks_the_wizard_backwards():
    s = Session()
    s.press("w:start")
    s.press("w:next")
    assert s.chat["setup_step"] == "rmax"
    s.press("w:back")
    assert s.chat["setup_step"] == "rmin"


# -- menu edits -------------------------------------------------------------

def test_egal_clears_a_value():
    s = Session()
    s.press("m:rent")
    s.press("set:rent:1200")
    assert s.filter["max_rent"] == 1200.0
    s.press(f"set:rent:{keyboards.ANY}")
    assert s.filter["max_rent"] is None


def test_room_bounds_cannot_cross():
    s = Session()
    s.press("set:rmin:3")
    s.press("set:rmax:2")
    f = s.filter
    assert f["rooms_min"] <= f["rooms_max"]


def test_ask_sets_awaiting_and_filter_reset_clears_everything():
    s = Session()
    s.press("ask:rent")
    assert s.chat["awaiting"] == "max_rent"

    db.update_filter(s.chat_id, {"max_rent": 900.0, "districts": "Mitte"})
    s.press("f:clear")
    f = s.filter
    assert f["max_rent"] is None and f["districts"] == ""


def test_toggling_all_districts_off_one_by_one_falls_back_to_no_filter():
    s = Session()
    for i in range(len(keyboards.DISTRICTS)):
        s.press(f"tog:d:{i}")
    assert s.filter["districts"] == ""


def test_out_of_range_district_index_is_ignored():
    s = Session()
    s.press("tog:d:99")
    assert s.filter["districts"] == ""


# -- robustness -------------------------------------------------------------

def test_a_stale_keyboard_reopens_a_fresh_menu():
    s = Session()
    q = s.press("m:rent", message_id=999)      # not the stored menu message

    assert q.answers and "veraltet" in q.answers[0]
    assert s.bot.sent, "a fresh menu should have been posted"
    assert s.chat["menu_msg_id"] == s.bot.sent[-1][2]


def test_delete_flow_removes_everything():
    s = Session()
    s.press("del:no")
    assert s.chat is not None
    s.press("del:yes")
    assert db.get_chat(s.chat_id) is None


def test_unknown_callback_is_ignored():
    s = Session()
    s.press("bogus:data")
    assert s.chat["state"] == "new"


# -- free-text input --------------------------------------------------------

class FakeMessage:
    def __init__(self, text):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


def _say(session: Session, text: str | None) -> FakeMessage:
    from app.handlers import text_input

    msg = FakeMessage(text)
    update = types.SimpleNamespace(
        effective_chat=types.SimpleNamespace(id=session.chat_id),
        effective_message=msg,
    )
    ctx = types.SimpleNamespace(bot=session.bot)
    asyncio.run(text_input.on_message(update, ctx))
    return msg


def test_free_text_lands_in_the_awaited_field():
    s = Session()
    s.press("ask:rent")
    _say(s, "1.250,50 €")
    assert s.filter["max_rent"] == 1250.5
    assert s.chat["awaiting"] == ""


def test_unparseable_input_keeps_the_prompt_open():
    s = Session()
    s.press("ask:rent")
    msg = _say(s, "keine Ahnung")
    assert "Zahl" in msg.replies[0]
    assert s.chat["awaiting"] == "max_rent"


def test_absurd_values_are_rejected():
    s = Session()
    s.press("ask:rent")
    msg = _say(s, "99999999")
    assert "unrealistisch" in msg.replies[0]
    assert s.filter["max_rent"] is None
    assert s.chat["awaiting"] == "max_rent"


def test_unexpected_text_gets_the_command_list_not_silence():
    s = Session()
    msg = _say(s, "hallo?")
    reply = msg.replies[0]
    for cmd in ("/start", "/filter", "/status", "/pause", "/resume",
                "/problem", "/stop", "/hilfe"):
        assert cmd in reply


def test_non_text_message_while_a_question_is_open_re_asks():
    """A sticker sent mid-prompt must not silently drop the user out of it."""
    s = Session()
    s.press("ask:rent")
    msg = _say(s, None)
    assert "Zahl" in msg.replies[0]
    assert s.chat["awaiting"] == "max_rent"


def test_non_text_message_outside_a_prompt_gets_the_command_list():
    s = Session()
    msg = _say(s, None)
    assert "/hilfe" in msg.replies[0]


def test_awaiting_survives_a_restart():
    """The prompt state lives in SQLite, not in a ConversationHandler, so a
    redeploy mid-question must not strand the user."""
    s = Session()
    s.press("ask:size")
    assert db.get_chat(s.chat_id)["awaiting"] == "min_size"
    _say(s, "60")
    assert s.filter["min_size"] == 60.0


# -- /problem ---------------------------------------------------------------

def test_problem_command_gives_the_support_address():
    from app import constants
    from app.handlers import commands

    s = Session()
    msg = FakeMessage("/problem")
    update = types.SimpleNamespace(
        effective_chat=types.SimpleNamespace(id=s.chat_id),
        effective_message=msg,
    )
    asyncio.run(commands.problem(update, types.SimpleNamespace(bot=s.bot)))
    assert constants.SUPPORT_EMAIL in msg.replies[0]


def test_support_address_is_plain_text_so_telegram_can_autolink_it():
    """A Markdown [label](mailto:…) is rejected by Telegram as a bad URL, so
    the address has to go out bare."""
    from app import constants, i18n
    for lang in i18n.SUPPORTED_LANGUAGES:
        problem = i18n.t("PROBLEM", lang, support_email=constants.SUPPORT_EMAIL)
        assert "mailto:" not in problem
        assert f"]({constants.SUPPORT_EMAIL}" not in problem


def test_problem_is_registered_as_a_command():
    from app.handlers.commands import COMMAND_NAMES
    assert "problem" in COMMAND_NAMES


# -- /language ----------------------------------------------------------------

def test_language_switch_confirms_in_the_new_language_and_refreshes_the_menu():
    s = Session()
    q = s.press("lang:en")
    assert "Language updated" in q.text
    assert s.chat["language"] == "en"
    assert s.bot.sent, "the currently open menu should have been refreshed"
    assert "Your filter" in s.bot.sent[-1][1]


def test_language_switch_rejects_unsupported_code():
    s = Session()
    q = s.press("lang:fr")
    assert q.text is None
    assert s.chat["language"] == "de"

