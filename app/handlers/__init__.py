"""Handler registration — one place that wires commands, buttons and text."""
from telegram import Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, MessageHandler,
    TypeHandler, filters,
)

from app.handlers import callbacks, commands, errors, text_input, tracking


def register_handlers(app: Application) -> None:
    # Group -1 runs first and logs every update without consuming it.
    app.add_handler(TypeHandler(Update, tracking.track), group=-1)

    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("filter", commands.filter_cmd))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("pause", commands.pause))
    app.add_handler(CommandHandler("resume", commands.resume))
    app.add_handler(CommandHandler("problem", commands.problem))
    app.add_handler(CommandHandler("stop", commands.stop))
    app.add_handler(CommandHandler(["hilfe", "help"], commands.help_cmd))

    app.add_handler(CallbackQueryHandler(callbacks.route))
    # Anything that isn't a command: free-text answers to a pending question,
    # and otherwise a short reminder of what this bot understands. Stickers and
    # photos land here too, so nothing a user sends is met with silence.
    app.add_handler(MessageHandler(
        ~filters.COMMAND & ~filters.StatusUpdate.ALL, text_input.on_message))

    app.add_error_handler(errors.on_error)
