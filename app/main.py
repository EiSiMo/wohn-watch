"""Entrypoint: one process running the Telegram bot and the scrape loop."""
import logging

from telegram import BotCommand
from telegram.ext import AIORateLimiter, Application

from app import db, settings
from app.handlers import register_handlers
from app.handlers.commands import COMMANDS
from app.services.scrape_job import prune_job, scrape_tick

logger = logging.getLogger("wohnwatch")

PRUNE_INTERVAL_SECONDS = 24 * 3600


async def _post_init(app: Application) -> None:
    await app.bot.set_my_commands([BotCommand(c, d) for c, d in COMMANDS])
    me = await app.bot.get_me()
    logger.info("running as @%s, %d chats, %d flats known",
                me.username, db.count_chats(), db.count_flats())


def build_app() -> Application:
    app = (
        Application.builder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        # Handles Telegram's ~30 msg/s ceiling and RetryAfter for us, which
        # matters once one new flat fans out to many chats at once.
        .rate_limiter(AIORateLimiter())
        .post_init(_post_init)
        .build()
    )
    register_handlers(app)
    app.job_queue.run_repeating(
        scrape_tick, interval=settings.SCRAPE_INTERVAL_SECONDS, first=5, name="scrape"
    )
    app.job_queue.run_repeating(
        prune_job, interval=PRUNE_INTERVAL_SECONDS, first=3600, name="prune"
    )
    return app


def main() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    db.init_db()
    app = build_app()
    logger.info("starting polling (interval=%ss)", settings.SCRAPE_INTERVAL_SECONDS)
    # Keep updates sent during a redeploy instead of dropping them.
    app.run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
