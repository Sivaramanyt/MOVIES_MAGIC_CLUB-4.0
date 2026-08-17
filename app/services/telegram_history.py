import logging

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, ChatAdminRequiredError, RPCError, UserNotParticipantError
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
        try:
            await self.client.start(bot_token=settings.bot_token.get_secret_value())

            me = await self.client.get_me()
            logger.info(
                "MTProto reindex session started: user_id=%s is_bot=%s",
                getattr(me, "id", "unknown"),
                getattr(me, "bot", False),
            )

            # A raw -100... Bot API channel ID is not enough by itself for
            # MTProto: Telethon needs the channel entity/access_hash. Reading
            # dialogs first obtains the entity when the bot is a member.
            dialogs = await self.client.get_dialogs(limit=None)
            entity = None
            for dialog in dialogs:
                candidate = getattr(dialog, "entity", None)
                if isinstance(candidate, Channel) and int(dialog.id) == int(channel_id):
                    entity = candidate
                    break

            if entity is None:
                # Try the normal resolver as a fallback in case the channel was
                # resolved but not returned as a dialog for this account.
                try:
                    candidate = await self.client.get_entity(int(channel_id))
                except ValueError as exc:
                    raise RuntimeError(
                        f"Channel {channel_id} is not visible to the reindex Telegram account. "
                        "Add the bot to that channel as an administrator and verify REINDEX_CHANNEL_ID."
                    ) from exc
                if not isinstance(candidate, Channel):
                    raise RuntimeError(
                        f"REINDEX_CHANNEL_ID {channel_id} does not resolve to a Telegram channel"
                    )
                entity = candidate

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
                f"The reindex Telegram account is not a member of channel {channel_id}. "
                "Add the bot to the channel as an administrator."
            ) from exc
        except ChannelPrivateError as exc:
            logger.exception("Channel %s is private/inaccessible to reindex account", channel_id)
            raise RuntimeError(
                f"Telegram reports channel {channel_id} is private or inaccessible. "
                "Make sure the bot is a member/admin of the channel."
            ) from exc
        except ChatAdminRequiredError as exc:
            logger.exception("Admin permission required for channel %s", channel_id)
            raise RuntimeError(
                f"Telegram requires administrator access to channel {channel_id}. "
                "Promote the bot to channel administrator and retry."
            ) from exc
        except RPCError as exc:
            logger.exception("Telegram history access failed for channel %s", channel_id)
            raise RuntimeError(
                f"Telegram history access failed for channel {channel_id}: {exc.__class__.__name__}"
            ) from exc
        finally:
            await self.client.disconnect()
