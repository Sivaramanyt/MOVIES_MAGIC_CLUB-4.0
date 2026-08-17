import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.movie_file_repository import MovieFileRepository
from app.database.repositories.movie_repository import MovieRepository
from app.parser.filename_parser import parse_filename
from app.tmdb import TMDBClient

logger = logging.getLogger(__name__)


@dataclass
class ReindexResult:
    scanned: int = 0
    files: int = 0
    created: int = 0
    existing: int = 0
    matched: int = 0
    unmatched: int = 0
    failed: int = 0


async def index_telegram_file(
    session: AsyncSession,
    *,
    channel_id: int,
    message_id: int,
    telegram_file_id: str,
    file_unique_id: str | None,
    filename: str,
    file_size: int | None,
    mime_type: str | None,
) -> tuple[str, bool]:
    """Persist one historical Telegram file and attach it to a TMDB movie when confident."""
    parsed = parse_filename(filename)
    file_repository = MovieFileRepository(session)
    row, created = await file_repository.create_or_get(
        channel_id=channel_id,
        message_id=message_id,
        telegram_file_id=telegram_file_id,
        file_unique_id=file_unique_id,
        filename=filename,
        file_size=file_size,
        mime_type=mime_type,
        parsed=parsed,
    )

    if not created:
        return "existing", False

    if not parsed.title:
        return "unmatched", True

    try:
        best, _ = await TMDBClient().match_movie(parsed.title, parsed.year)
        if not best:
            return "unmatched", True

        movie_repository = MovieRepository(session)
        movie, _ = await movie_repository.get_or_create_by_tmdb(
            tmdb_id=best.tmdb_id,
            title=best.title,
            original_title=best.original_title,
            release_date=best.release_date,
            year=best.year,
            overview=best.overview,
            poster_url=best.poster_url,
            backdrop_url=best.backdrop_url,
            rating=best.rating,
        )
        await file_repository.attach_movie(row, movie)
        await movie_repository.add_alias(movie, parsed.title)
        return "matched", True
    except Exception:
        logger.exception("TMDB matching failed for historical file %s", filename)
        return "unmatched", True


async def reindex_messages(session: AsyncSession, messages) -> ReindexResult:
    result = ReindexResult()
    for message in messages:
        result.scanned += 1
        document = getattr(message, "document", None)
        video = getattr(message, "video", None)
        media = document or video
        if media is None:
            continue

        result.files += 1
        try:
            telegram_file_id = f"mtproto:{media.id}:{getattr(media, 'access_hash', '')}"
            unique_id = str(media.id) if getattr(media, "id", None) is not None else None
            filename = getattr(getattr(message, "file", None), "name", None) or f"telegram_{message.id}.bin"
            file_size = getattr(getattr(message, "file", None), "size", None)
            mime_type = getattr(getattr(message, "file", None), "mime_type", None)

            status, created = await index_telegram_file(
                session,
                channel_id=int(message.chat_id),
                message_id=int(message.id),
                telegram_file_id=telegram_file_id,
                file_unique_id=unique_id,
                filename=filename,
                file_size=file_size,
                mime_type=mime_type,
            )
            if status == "existing":
                result.existing += 1
            elif status == "matched":
                result.created += int(created)
                result.matched += 1
            else:
                result.created += int(created)
                result.unmatched += 1
            await session.commit()
        except Exception:
            await session.rollback()
            result.failed += 1
            logger.exception("Historical file indexing failed for message %s", getattr(message, "id", "?"))

    return result
