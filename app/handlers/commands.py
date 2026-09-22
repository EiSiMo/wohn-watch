"""Slash commands."""
import logging

from telegram import BotCommand, BotCommandScopeChat, Update
from telegram.ext import ContextTypes

from app import constants, db, formatting, i18n, keyboards
from app.handlers import _ui

logger = logging.getLogger("wohnwatch.commands")

# Language-independent command identifiers, used both to derive CMD_DESC_*
# i18n keys and to build the BotFather menu.
COMMAND_NAMES = ("start", "filter", "status", "pause", "resume", "problem", "stop", "language")

# The two commands whose *trigger word* itself differs by language (both
# words stay registered in handlers/__init__.py regardless of the chat's
# current language, so switching never breaks a command).
_WORD = {
    "help": {"de": "hilfe", "en": "help"},
    "language": {"de": "sprache", "en": "language"},
}


def commands_for_menu(lang: str) -> list[BotCommand]:
    names = [*COMMAND_NAMES, "help"]
    return [
        BotCommand(_WORD.get(name, {}).get(lang, name), i18n.t(f"CMD_DESC_{name.upper()}", lang))
        for name in names
    ]


async def sync_command_scope(bot, chat_id: int, lang: str) -> None:
    """set_my_commands(language_code=...) (see main.py's _post_init) is keyed
    off the Telegram *client's* language setting, not anything this bot
    decides — so it never follows a chat's own /language choice. A per-chat
    BotCommandScopeChat overrides that for this one chat regardless of the
    client's language, which is what actually makes the "/" menu follow
    /sprache."""
    await bot.set_my_commands(commands_for_menu(lang), scope=BotCommandScopeChat(chat_id))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    db.set_chat(chat_id, awaiting="")
    lang = chat["language"]
    await sync_command_scope(context.bot, chat_id, lang)

    if chat["state"] in ("active", "paused"):
        await _ui.reply(update, i18n.t("INTRO_RETURNING", lang,
            summary=formatting.filter_summary(db.get_filter(chat_id), lang),
            state=_ui.state_label(chat, lang),
        ))
        return

    await _ui.send_menu(context.bot, chat_id, i18n.t("INTRO", lang), keyboards.render_intro(lang))


async def filter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    lang = chat["language"]
    # Leaving the wizard: /filter always lands on the root menu.
    db.set_chat(chat_id, setup_step="", awaiting="")
    text, markup = keyboards.render_root(db.get_filter(chat_id), lang)
    await _ui.send_menu(context.bot, chat_id, text, markup)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    if not chat or chat["state"] == "new":
        await _ui.reply(update, i18n.t("NOT_SET_UP", lang))
        return
    last = db.get_meta("last_scrape_at") or "—"
    await _ui.reply(update, i18n.t("STATUS", lang,
        state=_ui.state_label(chat, lang),
        summary=formatting.filter_summary(db.get_filter(chat_id), lang),
        sent=db.count_notifications(chat_id),
        flats=db.count_flats(),
        last_scrape=(last[:19].replace("T", " ") + " UTC") if last != "—" else last,
    ))


async def pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    if not chat or chat["state"] == "new":
        await _ui.reply(update, i18n.t("NOT_SET_UP", lang))
        return
    if chat["state"] == "paused":
        await _ui.reply(update, i18n.t("ALREADY_PAUSED", lang))
        return
    db.set_chat(chat_id, state="paused")
    await _ui.reply(update, i18n.t("PAUSED", lang))


async def resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.get_chat(chat_id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    if not chat or chat["state"] == "new":
        await _ui.reply(update, i18n.t("NOT_SET_UP", lang))
        return
    if chat["state"] == "active":
        await _ui.reply(update, i18n.t("ALREADY_ACTIVE", lang))
        return
    # Bump the watermark: un-pausing after a week must not dump a week of listings.
    _ui.activate(chat_id)
    await _ui.reply(update, i18n.t("RESUMED", lang))


async def problem(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # The address goes out as plain text on purpose: Telegram auto-links email
    # addresses, while a Markdown [label](mailto:…) is rejected as a bad URL.
    chat = db.get_chat(update.effective_chat.id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    await _ui.reply(update, i18n.t("PROBLEM", lang, support_email=constants.SUPPORT_EMAIL))


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = db.get_chat(update.effective_chat.id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    await _ui.reply(update, i18n.t("DELETE_CONFIRM", lang), keyboards.render_delete_confirm(lang))


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = db.get_chat(update.effective_chat.id)
    lang = chat["language"] if chat else i18n.DEFAULT_LANGUAGE
    await _ui.reply(update, i18n.t("HELP", lang))


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    chat = db.ensure_chat(chat_id)
    lang = chat["language"]
    await _ui.reply(update, i18n.t("LANGUAGE_PROMPT", lang), keyboards.render_language_picker(lang))
