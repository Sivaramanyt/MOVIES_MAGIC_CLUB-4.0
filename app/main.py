import logging
from contextlib import asynccontextmanager

from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request

from app.bot import create_bot, create_dispatcher
from app.config import get_settings
from app.database.session import check_database_connection, close_database

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

bot = create_bot(settings.bot_token.get_secret_value())
dispatcher = create_dispatcher()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MOVIES MAGIC CLUB 4.0")
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.webhook_secret,
        allowed_updates=dispatcher.resolve_used_update_types(),
        drop_pending_updates=False,
    )
    logger.info("Telegram webhook configured: %s", settings.webhook_url)
    yield
    await bot.session.close()
    await close_database()
    logger.info("Application shutdown complete")


app = FastAPI(title="MOVIES MAGIC CLUB 4.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    database_ok = await check_database_connection()
    return {
        "status": "ok" if database_ok else "degraded",
        "database": "ok" if database_ok else "unavailable",
    }


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    payload = await request.json()
    update = Update.model_validate(payload)
    await dispatcher.feed_update(bot, update)
    return {"status": "ok"}
