import asyncio
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import get_settings
from app.services.telegram_history import ChannelHistoryIndexer

router = Router()
settings = get_settings()
logger = logging.getLogger(__name__)
_reindex_lock = asyncio.Lock()


def _is_admin(message: Message) -> bool:
    admin_ids = {
        int(value.strip())
        for value in settings.admin_user_ids.split(",")
        if value.strip().isdigit()
    }
    return message.from_user is not None and message.from_user.id in admin_ids


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
            "• REINDEX_CHANNEL_ID\n\n"
            "The existing BOT_TOKEN is used for Telegram access."
        )
        return

    if _reindex_lock.locked():
        await message.answer("⏳ A channel reindex is already running. Please wait for it to finish.")
        return

    argument = (message.text or "").partition(" ")[2].strip()
    limit = settings.reindex_max_messages
    if argument:
        if not argument.isdigit():
            await message.answer("Usage: <code>/reindex</code> or <code>/reindex 100</code>")
            return
        limit = min(max(int(argument), 1), settings.reindex_max_messages)

    await message.answer(
        "📚 <b>Channel reindex started</b>\n\n"
        f"Channel: <code>{settings.reindex_channel_id}</code>\n"
        f"Maximum messages: <b>{limit}</b>\n\n"
        "This scans old Telegram channel history, stores new files, parses metadata, "
        "matches high-confidence TMDB results, and groups files by TMDB ID.\n\n"
        "⏳ Please wait…"
    )

    async def run() -> None:
        async with _reindex_lock:
            try:
                indexer = ChannelHistoryIndexer()
                result = await indexer.reindex(
                    channel_id=settings.reindex_channel_id,
                    limit=limit,
                )
                await message.answer(
                    "📚 <b>Channel Reindex Complete</b>\n\n"
                    f"Messages scanned: {result.scanned}\n"
                    f"Movie files found: {result.files}\n"
                    f"New records: {result.created}\n"
                    f"Already indexed: {result.existing}\n"
                    f"TMDB matched: {result.matched}\n"
                    f"Unmatched: {result.unmatched}\n"
                    f"Failed: {result.failed}\n\n"
                    "Database: ✅\n"
                    "Duplicates: prevented by channel + message ID"
                )
            except Exception:
                logger.exception("Channel reindex failed")
                await message.answer(
                    "❌ <b>Channel reindex failed.</b>\n\n"
                    "Check Koyeb logs. Existing database records were not deleted."
                )

    asyncio.create_task(run())
