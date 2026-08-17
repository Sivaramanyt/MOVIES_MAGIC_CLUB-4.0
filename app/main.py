import logging
from contextlib import asynccontextmanager

from aiogram import Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import create_bot, router as bot_router
from app.config import get_settings
from app.database.file_intake_diagnostics import run_file_intake_smoke_test
from app.database.repository_diagnostics import run_movie_repository_smoke_test
from app.database.session import SessionLocal, check_database_connection, close_database
from app.diagnostics import get_database_diagnostics
from app.reindex_bot import router as reindex_router

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

bot = create_bot(settings.bot_token.get_secret_value())

# Router order matters in aiogram.  The normal bot router has a catch-all
# message handler, so the admin command router must be registered first.
dispatcher = Dispatcher()
dispatcher.include_router(reindex_router)
dispatcher.include_router(bot_router)


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


@app.get("/admin/diagnostics/database")
async def database_diagnostics(
    x_admin_diagnostics_token: str | None = Header(default=None),
) -> dict:
    if x_admin_diagnostics_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    try:
        return await get_database_diagnostics()
    except Exception:
        logger.exception("Database diagnostics failed")
        raise HTTPException(status_code=503, detail="Database diagnostics unavailable")


@app.post("/admin/diagnostics/repository-smoke-test")
async def repository_smoke_test(
    x_admin_diagnostics_token: str | None = Header(default=None),
) -> dict:
    if x_admin_diagnostics_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    session: AsyncSession = SessionLocal()
    try:
        return await run_movie_repository_smoke_test(session)
    except Exception:
        logger.exception("Movie repository smoke test failed")
        raise HTTPException(status_code=503, detail="Repository smoke test failed")
    finally:
        await session.close()


@app.post("/admin/diagnostics/file-intake-smoke-test")
async def file_intake_smoke_test(
    x_admin_diagnostics_token: str | None = Header(default=None),
) -> dict:
    if x_admin_diagnostics_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    session: AsyncSession = SessionLocal()
    try:
        return await run_file_intake_smoke_test(session)
    except Exception:
        logger.exception("File intake smoke test failed")
        raise HTTPException(status_code=503, detail="File intake smoke test failed")
    finally:
        await session.close()


@app.post(settings.webhook_path)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, str]:
    if x_telegram_bot_api_secret_token != settings.webhook_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    try:
        payload = await request.json()
        update = Update.model_validate(payload)
        await dispatcher.feed_update(bot, update)
    except Exception:
        logger.exception("Telegram update processing failed")
        return {"status": "accepted", "processing": "failed"}

    return {"status": "ok"}
