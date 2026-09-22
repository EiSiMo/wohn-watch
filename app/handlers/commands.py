"""Slash commands."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app import db, formatting, keyboards, texts
from app.handlers import _ui

logger = logging.getLogger("wohnwatch.commands")

COMMANDS = [
    ("start", "Einführung und Einrichtung"),
    ("filter", "Suche ändern"),
    ("status", "Filter und Statistik"),
    ("pause", "Benachrichtigungen aussetzen"),
    ("resume", "Benachrichtigungen fortsetzen"),
    ("problem", "Problem melden"),
    ("stop", "Alle Daten löschen"),
    ("hilfe", "Übersicht aller Befehle"),
]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    db.set_chat(chat_id, awaiting="")

    if chat["state"] in ("active", "paused"):
        await _ui.reply(update, texts.INTRO_RETURNING.format(
            summary=formatting.filter_summary(db.get_filter(chat_id)),
            state=_ui.state_label(chat),
        ))
        return

    await _ui.send_menu(context.bot, chat_id, texts.INTRO, keyboards.render_intro())


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    db.ensure_chat(chat_id)
    # Leaving the wizard: /filter always lands on the root menu.
    db.set_chat(chat_id, setup_step="", awaiting="")
    text, markup = keyboards.render_root(db.get_filter(chat_id))
    await _ui.send_menu(context.bot, chat_id, text, markup)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    if not chat or chat["state"] == "new":
        await _ui.reply(update, texts.NOT_SET_UP)
        return
    last = db.get_meta("last_scrape_at") or "—"
    await _ui.reply(update, texts.STATUS.format(
        state=_ui.state_label(chat),
        summary=formatting.filter_summary(db.get_filter(chat_id)),
        sent=db.count_notifications(chat_id),
        flats=db.count_flats(),
        last_scrape=(last[:19].replace("T", " ") + " UTC") if last != "—" else last,
    ))


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    if not chat or chat["state"] == "new":
        await _ui.reply(update, texts.NOT_SET_UP)
        return
    if chat["state"] == "paused":
        await _ui.reply(update, texts.ALREADY_PAUSED)
        return
    db.set_chat(chat_id, state="paused")
    await _ui.reply(update, texts.PAUSED)


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    if not chat or chat["state"] == "new":
        await _ui.reply(update, texts.NOT_SET_UP)
        return
    if chat["state"] == "active":
        await _ui.reply(update, texts.ALREADY_ACTIVE)
        return
    # Bump the watermark: un-pausing after a week must not dump a week of listings.
    _ui.activate(chat_id)
    await _ui.reply(update, texts.RESUMED)


async def problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # The address goes out as plain text on purpose: Telegram auto-links email
    # addresses, while a Markdown [label](mailto:…) is rejected as a bad URL.
    await _ui.reply(update, texts.PROBLEM)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ui.reply(update, texts.DELETE_CONFIRM, keyboards.render_delete_confirm())


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _ui.reply(update, texts.HELP)
