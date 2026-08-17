import logging

from telethon import TelegramClient
from telethon.errors import RPCError
from telethon.sessions import MemorySession
from telethon.tl.types import Channel

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
            # Warm the MTProto entity cache. This is important when the channel
            # is configured with a Bot API-style -100... channel ID.
            await self.client.get_dialogs(limit=None)
            entity = await self.client.get_entity(channel_id)

            if not isinstance(entity, Channel):
                raise RuntimeError(
                    f"Configured reindex ID {channel_id} is not a Telegram channel"
                )

            logger.info(
                "Reindexing Telegram channel id=%s title=%s limit=%s",
                channel_id,
                getattr(entity, "title", "unknown"),
                limit,
            )

            messages = self.client.iter_messages(entity, limit=limit)
            session = SessionLocal()
            try:
                return await reindex_messages(session, messages)
            finally:
                await session.close()
        except RPCError as exc:
            logger.exception("Telegram history access failed for channel %s", channel_id)
            raise RuntimeError(
                f"Telegram could not read channel {channel_id}: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.client.disconnect()
