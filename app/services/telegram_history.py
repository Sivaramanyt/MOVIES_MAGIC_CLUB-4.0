import logging

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError, RPCError, UserNotParticipantError
from telethon.sessions import StringSession
from telethon.tl.types import Channel

from app.config import get_settings
from app.database.session import SessionLocal
from app.services.channel_reindexer import ReindexResult, reindex_messages

logger = logging.getLogger(__name__)
settings = get_settings()


class ChannelHistoryIndexer:
    """Read channel history through a user MTProto session and persist movie files.

    Telegram Bot API tokens cannot be used for arbitrary historical channel
    history. A user-authorized Telethon StringSession is required for bulk
    history reads. The normal aiogram webhook continues to use BOT_TOKEN.
    """

    def __init__(self) -> None:
        if not settings.reindex_configured:
            raise RuntimeError(
                "Channel reindex is not configured. Set TELEGRAM_API_ID, "
                "TELEGRAM_API_HASH, REINDEX_SESSION_STRING and REINDEX_CHANNEL_ID."
            )
        self.client = TelegramClient(
            StringSession(settings.reindex_session_string.get_secret_value()),
            settings.telegram_api_id,
            settings.telegram_api_hash.get_secret_value(),
        )

    async def reindex(self, *, channel_id: int, limit: int) -> ReindexResult:
        try:
            await self.client.connect()
            if not await self.client.is_user_authorized():
                raise RuntimeError(
                    "The REINDEX_SESSION_STRING is not authorized. Create a user Telethon session and update Koyeb."
                )

            me = await self.client.get_me()
            if getattr(me, "bot", False):
                raise RuntimeError(
                    "REINDEX_SESSION_STRING belongs to a Telegram bot. Use a normal Telegram user account session for historical indexing."
                )
            logger.info("MTProto user session started: user_id=%s", getattr(me, "id", "unknown"))

            try:
                entity = await self.client.get_entity(int(channel_id))
            except (ValueError, TypeError) as exc:
                raise RuntimeError(
                    f"Channel {channel_id} is not visible to the reindex user account. "
                    "Make sure that account is a member of the channel and verify REINDEX_CHANNEL_ID."
                ) from exc

            if not isinstance(entity, Channel):
                raise RuntimeError(f"REINDEX_CHANNEL_ID {channel_id} does not resolve to a Telegram channel")

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

        except UserNotParticipantError as exc:
            logger.exception("Reindex account is not a member of channel %s", channel_id)
            raise RuntimeError(
                f"The reindex user account is not a member of channel {channel_id}. Join the channel with that account and retry."
            ) from exc
        except ChannelPrivateError as exc:
            logger.exception("Channel %s is private/inaccessible to reindex account", channel_id)
            raise RuntimeError(
                f"Telegram reports channel {channel_id} is private or inaccessible to the reindex user account."
            ) from exc
        except ChatAdminRequiredError as exc:
            logger.exception("Admin permission required for channel %s", channel_id)
            raise RuntimeError(
                f"Telegram requires administrator access to channel {channel_id}. Give the reindex user account sufficient channel access and retry."
            ) from exc
        except RPCError as exc:
            logger.exception("Telegram history access failed for channel %s", channel_id)
            raise RuntimeError(
                f"Telegram history access failed for channel {channel_id}: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.client.disconnect()
