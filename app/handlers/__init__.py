"""Handler registration — one place that wires commands, buttons and text."""
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters,
)

from app.handlers import callbacks, commands, errors, text_input


def register_handlers(app: Application) -> None:
    app.add_handler(CommandHandler("start", commands.start))
    app.add_handler(CommandHandler("filter", commands.filter_cmd))
    app.add_handler(CommandHandler("status", commands.status))
    app.add_handler(CommandHandler("pause", commands.pause))
    app.add_handler(CommandHandler("resume", commands.resume))
    app.add_handler(CommandHandler("stop", commands.stop))
    app.add_handler(CommandHandler(["hilfe", "help"], commands.help_cmd))

    app.add_handler(CallbackQueryHandler(callbacks.route))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_input.on_text))

    app.add_error_handler(errors.on_error)
