from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MovieFile


class MovieFileRepository:
    """Database access for Telegram files indexed into movie groups."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_channel_message(
        self, *, channel_id: int, message_id: int
    ) -> MovieFile | None:
        result = await self.session.execute(
            select(MovieFile).where(
                MovieFile.channel_id == channel_id,
                MovieFile.message_id == message_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_file_unique_id(self, file_unique_id: str) -> MovieFile | None:
        result = await self.session.execute(
            select(MovieFile).where(MovieFile.file_unique_id == file_unique_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        movie_id: int,
        channel_id: int,
        message_id: int,
        telegram_file_id: str,
        file_unique_id: str | None,
        filename: str,
        language: str | None = None,
        quality: str | None = None,
        file_size: int | None = None,
        mime_type: str | None = None,
    ) -> MovieFile:
        existing = await self.get_by_channel_message(
            channel_id=channel_id, message_id=message_id
        )
        if existing is not None:
            return existing

        file = MovieFile(
            movie_id=movie_id,
            channel_id=channel_id,
            message_id=message_id,
            telegram_file_id=telegram_file_id,
            file_unique_id=file_unique_id,
            filename=filename,
            language=language,
            quality=quality,
            file_size=file_size,
            mime_type=mime_type,
            indexed=True,
        )
        self.session.add(file)
        await self.session.flush()
        return file
