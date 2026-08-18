from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Movie, MovieFile
from app.parser.filename_parser import ParsedFilename


class MovieFileRepository:
    """Persistence for Telegram files and parsed metadata before/after TMDB matching."""

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

    async def create_or_get(
        self,
        *,
        channel_id: int,
        message_id: int,
        telegram_file_id: str,
        file_unique_id: str | None,
        filename: str,
        file_size: int | None,
        mime_type: str | None,
        parsed: ParsedFilename | None = None,
    ) -> tuple[MovieFile, bool]:
        existing = await self.get_by_channel_message(channel_id, message_id)
        if existing is not None:
            return existing, False

        row = MovieFile(
            channel_id=channel_id,
            message_id=message_id,
            telegram_file_id=telegram_file_id,
            file_unique_id=file_unique_id,
            filename=filename,
            parsed_title=parsed.title if parsed else None,
            parsed_year=parsed.year if parsed else None,
            language=parsed.language if parsed else None,
            quality=parsed.quality if parsed else None,
            source=parsed.source if parsed else None,
            codec=parsed.codec if parsed else None,
            audio=parsed.audio if parsed else None,
            extension=parsed.extension if parsed else None,
            file_size=file_size,
            mime_type=mime_type,
            indexed=True,
            movie_id=None,
        )
        self.session.add(row)
        await self.session.flush()
        return row, True

    async def update_parsed_metadata(self, row: MovieFile, parsed: ParsedFilename) -> MovieFile:
        """Update only parser-derived metadata; never changes identity or movie linkage."""
        row.parsed_title = parsed.title or None
        row.parsed_year = parsed.year
        row.language = parsed.language
        row.quality = parsed.quality
        row.source = parsed.source
        row.codec = parsed.codec
        row.audio = parsed.audio
        row.extension = parsed.extension
        await self.session.flush()
        return row

    async def attach_movie(self, row: MovieFile, movie: Movie) -> MovieFile:
        row.movie_id = movie.id
        await self.session.flush()
        return row
