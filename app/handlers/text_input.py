"""Free-text input for the numeric filter values.

`chats.awaiting` holds the field the bot is waiting for. Because that lives in
SQLite rather than in a ConversationHandler's memory, a restart mid-prompt is
harmless: the user's next message still lands in the right slot.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app import db, formatting, i18n, keyboards
from app.handlers import _ui
from app.handlers.callbacks import _fix_room_bounds

logger = logging.getLogger("wohnwatch.text")

_SCREEN_OF_FIELD = {
    "rooms_min": "rmin", "rooms_max": "rmax",
    "max_rent": "rent", "min_size": "size",
}


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    lang = chat["language"]
    field = chat["awaiting"]
    text = update.effective_message.text

    if field not in keyboards.INPUT_RANGES:
        await _ui.reply(update, i18n.t("UNEXPECTED_TEXT", lang))
        return

    if text is None:
        # A sticker or photo while we're waiting for a number: re-ask instead
        # of dropping the user out of the prompt.
        await _ui.reply(update, i18n.t("BAD_NUMBER", lang))
        return

    raw = text.strip()
    value = formatting.parse_number(raw, lang)
    lo, hi = keyboards.INPUT_RANGES[field]

    if value == 0.0:
        await _ui.reply(update, i18n.t("BAD_NUMBER", lang))
        return
    if not lo <= value <= hi:
        await _ui.reply(update, i18n.t("OUT_OF_RANGE", lang, lo="%g" % lo, hi="%g" % hi))
        return

    db.update_filter(chat_id, {field: value})
    _fix_room_bounds(chat_id, field)
    db.set_chat(chat_id, awaiting="")

    screen = _SCREEN_OF_FIELD[field]
    wizard = chat["state"] == "setup"
    text, markup = keyboards.render_screen(screen, db.get_filter(chat_id), lang, wizard=wizard)

    edited = False
    if chat["menu_msg_id"]:
        edited = await _ui.edit_menu_by_id(
            context.bot, chat_id, chat["menu_msg_id"], text, markup
        )
    if not edited:
        await _ui.send_menu(context.bot, chat_id, text, markup)
