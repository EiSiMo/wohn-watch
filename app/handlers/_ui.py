"""Shared helpers for rendering the one menu message per chat."""
import logging

from telegram import Bot, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.error import BadRequest

from app import db

logger = logging.getLogger("wohnwatch.ui")

MD = ParseMode.MARKDOWN


async def send_menu(bot: Bot, chat_id: int, text: str,
                    markup: InlineKeyboardMarkup | None = None) -> None:
    """Post a fresh menu message and make it the one this chat edits from now on."""
    msg = await bot.send_message(
        chat_id, text, parse_mode=MD, reply_markup=markup,
        disable_web_page_preview=True,
    )
    db.set_chat(chat_id, menu_msg_id=msg.message_id)


async def edit_menu(query, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    """Edit the menu in place. "not modified" is a no-op, not an error."""
    try:
        await query.edit_message_text(
            text, parse_mode=MD, reply_markup=markup, disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            raise


async def reply(update, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    await update.effective_message.reply_text(
        text, parse_mode=MD, reply_markup=markup, disable_web_page_preview=True,
    )


def activate(chat_id: int) -> None:
    """Turn alerts on and set the cold-start watermark.

    notify_since is what keeps a brand-new chat from being buried under the
    couple hundred listings already in the database.
    """
    db.set_chat(
        chat_id, state="active", setup_step="", awaiting="", notify_since=db.now_iso()
    )


def state_label(chat: dict | None) -> str:
    from app import texts

    if not chat or chat["state"] in ("new", "setup"):
        return texts.STATE_NEW
    return texts.STATE_ACTIVE if chat["state"] == "active" else texts.STATE_PAUSED


async def edit_menu_by_id(bot: Bot, chat_id: int, message_id: int, text: str,
                          markup: InlineKeyboardMarkup | None = None) -> bool:
    """Edit the stored menu message from outside a callback (after free-text
    input). Returns False when the message is gone and a fresh one is needed."""
    try:
        await bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id, parse_mode=MD,
            reply_markup=markup, disable_web_page_preview=True,
        )
        return True
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return True
        logger.info("menu edit failed for chat=%s: %s", chat_id, e)
        return False
