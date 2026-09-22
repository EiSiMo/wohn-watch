"""Usage log.

Registered in group -1, so it sees every update before any other handler and
records it regardless of which handler ends up doing the work. It never stops
propagation and never raises — a logging failure must not cost a user their
reply.

Ensuring the chat row here also guarantees events always have a parent to hang
off, which matters because events cascade away with the chat on /stop.
"""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from app import db, i18n

logger = logging.getLogger("wohnwatch.tracking")


def _classify(update: Update) -> tuple[str, str]:
    """(kind, detail) for one incoming update."""
    if update.callback_query is not None:
        return "callback", update.callback_query.data or ""

    msg = update.effective_message
    if msg is None:
        return "other", update.__class__.__name__

    if msg.text:
        if msg.text.startswith("/"):
            # Just the command word: /filter@botname and its arguments would
            # only make the counts noisy.
            return "command", msg.text.split()[0].split("@")[0].lower()
        return "text", msg.text

    for attr in ("photo", "sticker", "document", "voice", "video", "audio",
                 "animation", "location", "contact"):
        if getattr(msg, attr, None):
            return "media", attr
    return "other", "message"


async def track(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        chat = update.effective_chat
        if chat is None:
            return
        user = getattr(update, "effective_user", None)
        code = getattr(user, "language_code", None) if user else None
        db.ensure_chat(chat.id, language=i18n.resolve_language(code))
        kind, detail = _classify(update)
        db.log_event(chat.id, "in", kind, detail)
    except Exception:
        logger.exception("tracking failed")
