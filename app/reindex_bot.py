import asyncio
import html
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.services.index_control import index_controller
from app.services.telegram_history import ChannelHistoryIndexer

router = Router()
settings = get_settings()
logger = logging.getLogger(__name__)


def _is_admin(message: Message) -> bool:
    configured = getattr(settings, "admin_user_ids", "") or ""
    admin_ids = {int(value.strip()) for value in configured.split(",") if value.strip().isdigit()}
    return message.from_user is not None and message.from_user.id in admin_ids


def _progress_text(prefix: str = "📊 <b>Index Status</b>") -> str:
    p = index_controller.snapshot()
    state = "running"
    if p.paused:
        state = "paused"
    if p.stop_requested:
        state = "stopping"
    if not p.running:
        state = "idle"
    return (
        f"{prefix}\n\n"
        f"State: <b>{state}</b>\n"
        f"Channel: <code>{p.channel_id or '-'}</code>\n"
        f"Limit: <b>{p.limit or '-'}</b>\n"
        f"Scanned: <b>{p.scanned}</b>\n"
        f"Files: <b>{p.files}</b>\n"
        f"New: <b>{p.created}</b>\n"
        f"Existing: <b>{p.existing}</b>\n"
        f"TMDB matched: <b>{p.matched}</b>\n"
        f"Unmatched: <b>{p.unmatched}</b>\n"
        f"Failed: <b>{p.failed}</b>"
    )


@router.message(Command("index_status"))
async def index_status_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to view index status.")
        return
    await message.answer(_progress_text())


@router.message(Command("index_pause"))
async def index_pause_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to control indexing.")
        return
    if await index_controller.pause():
        await message.answer("⏸ <b>Bulk indexing paused.</b>\n\n" + _progress_text("Current progress"))
    else:
        await message.answer("ℹ️ No running bulk index is available to pause.")


@router.message(Command("index_resume"))
async def index_resume_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to control indexing.")
        return
    if await index_controller.resume():
        await message.answer("▶️ <b>Bulk indexing resumed.</b>\n\n" + _progress_text("Current progress"))
    else:
        await message.answer("ℹ️ No paused bulk index is available to resume.")


@router.message(Command("index_stop"))
async def index_stop_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to control indexing.")
        return
    if await index_controller.stop():
        await message.answer("🛑 <b>Stop requested.</b>\n\nThe current message will finish safely, then indexing will stop.\n\n" + _progress_text("Current progress"))
    else:
        await message.answer("ℹ️ No running bulk index is available to stop.")


@router.message(Command("reindex"))
async def reindex_handler(message: Message) -> None:
    if not _is_admin(message):
        await message.answer("⛔ You are not authorized to run reindex.")
        return

    if not settings.reindex_configured:
        await message.answer(
            "⚠️ <b>Channel reindex is not configured.</b>\n\n"
            "Koyeb needs:\n"
            "• TELEGRAM_API_ID\n"
            "• TELEGRAM_API_HASH\n"
            "• REINDEX_CHANNEL_ID"
        )
        return

    argument = (message.text or "").partition(" ")[2].strip()
    limit = settings.reindex_max_messages
    if argument:
        if not argument.isdigit():
            await message.answer("Usage: <code>/reindex</code> or <code>/reindex 100</code>")
            return
        limit = min(max(int(argument), 1), settings.reindex_max_messages)

    if not await index_controller.start(settings.reindex_channel_id, limit):
        await message.answer("⏳ A bulk index is already running. Use /index_status, /index_pause, /index_resume or /index_stop.")
        return

    await message.answer(
        "📚 <b>Bulk channel indexing started</b>\n\n"
        f"Channel: <code>{settings.reindex_channel_id}</code>\n"
        f"Maximum messages: <b>{limit}</b>\n\n"
        "Idempotent database writes are enabled. TMDB processing retries transient failures safely.\n\n"
        "Controls: /index_status · /index_pause · /index_resume · /index_stop"
    )

    async def run() -> None:
        try:
            indexer = ChannelHistoryIndexer()
            result = await indexer.reindex(channel_id=settings.reindex_channel_id, limit=limit)
            p = index_controller.snapshot()
            stopped = p.stop_requested
            await message.answer(
                "🛑 <b>Bulk index stopped safely</b>" if stopped else "📚 <b>Bulk Channel Index Complete</b>"
                + "\n\n"
                f"Messages scanned: {result.scanned}\n"
                f"Movie files found: {result.files}\n"
                f"New records: {result.created}\n"
                f"Already indexed: {result.existing}\n"
                f"TMDB matched: {result.matched}\n"
                f"Unmatched: {result.unmatched}\n"
                f"Failed: {result.failed}\n\n"
                "Duplicates: prevented by channel + message ID"
            )
        except Exception as exc:
            logger.exception("Channel reindex failed")
            safe_reason = html.escape(str(exc).strip() or exc.__class__.__name__)[:300]
            await message.answer(
                "❌ <b>Channel reindex failed.</b>\n\n"
                f"Reason: <code>{safe_reason}</code>\n\n"
                "Existing database records were not deleted."
            )
        finally:
            await index_controller.finish()

    asyncio.create_task(run())
