"""Global error handler — a broken update must never take the bot down."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger("wohnwatch.errors")


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id if isinstance(update, Update) and update.effective_chat else None
    logger.exception("unhandled error (chat=%s)", chat_id, exc_info=context.error)
