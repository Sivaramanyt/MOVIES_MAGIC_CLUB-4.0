import logging

from telethon import TelegramClient
from telethon.sessions import MemorySession

from app.config import get_settings
from app.database.session import SessionLocal
from app.services.channel_reindexer import ReindexResult, reindex_messages

logger = logging.getLogger(__name__)
settings = get_settings()


class ChannelHistoryIndexer:
    """Read channel history through MTProto and persist movie files."""

    def __init__(self) -> None:
        if not settings.reindex_configured:
            raise RuntimeError("Channel reindex is not configured")
        self.client = TelegramClient(
            MemorySession(),
            settings.telegram_api_id,
            settings.telegram_api_hash.get_secret_value(),
        )

    async def reindex(self, *, channel_id: int, limit: int) -> ReindexResult:
        await self.client.start(bot_token=settings.bot_token.get_secret_value())
        try:
            messages = self.client.iter_messages(channel_id, limit=limit)
            session = SessionLocal()
            try:
                return await reindex_messages(session, messages)
            finally:
                await session.close()
        finally:
            await self.client.disconnect()
