"""Sending one match to one chat."""
import logging

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import BadRequest

from app.formatting import render_match

logger = logging.getLogger("wohnwatch.notify")


async def send_match(bot: Bot, chat_id: int, flat: dict) -> None:
    """Send a match, falling back to plain text if Telegram rejects the Markdown.

    An address containing _ * [ or ` makes legacy Markdown parsing fail with
    400 — without this fallback the user would silently lose the alert.
    """
    markdown, plain = render_match(flat)
    try:
        await bot.send_message(
            chat_id, markdown, parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True,
        )
    except BadRequest as e:
        if "parse entities" not in str(e).lower() and "parse" not in str(e).lower():
            raise
        logger.info("markdown rejected for flat=%s, sending plain: %s", flat.get("id"), e)
        await bot.send_message(chat_id, plain, disable_web_page_preview=True)
