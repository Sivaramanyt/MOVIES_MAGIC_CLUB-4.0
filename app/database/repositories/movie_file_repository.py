from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MovieFile


class MovieFileRepository:
    """Persistence for raw Telegram file metadata before movie grouping."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_channel_message(self, channel_id: int, message_id: int) -> MovieFile | None:
        result = await self.session.execute(
            select(MovieFile).where(
                MovieFile.channel_id == channel_id,
                MovieFile.message_id == message_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_or_get(self, *, channel_id: int, message_id: int, telegram_file_id: str, file_unique_id: str | None, filename: str, file_size: int | None, mime_type: str | None) -> tuple[MovieFile, bool]:
        existing = await self.get_by_channel_message(channel_id, message_id)
        if existing is not None:
            return existing, False
        row = MovieFile(
            channel_id=channel_id,
            message_id=message_id,
            telegram_file_id=telegram_file_id,
            file_unique_id=file_unique_id,
            filename=filename,
            file_size=file_size,
            mime_type=mime_type,
            indexed=True,
            movie_id=None,
        )
        self.session.add(row)
        await self.session.flush()
        return row, True
