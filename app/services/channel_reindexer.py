import asyncio
import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.movie_file_repository import MovieFileRepository
from app.database.repositories.movie_repository import MovieRepository
from app.parser.filename_parser import parse_filename
from app.services.index_control import index_controller
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


async def _tmdb_match_with_retry(title: str, year: int | None):
    last_error = None
    for attempt in range(3):
        try:
            return await TMDBClient().match_movie(title, year)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise last_error


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
    """Idempotently persist one historical file and retry TMDB before giving up."""
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
        # Existing rows are intentionally never duplicated. If already grouped,
        # leave them untouched; otherwise this pass can safely retry TMDB work.
        if row.movie_id is not None:
            return "existing", False

    if not parsed.title:
        return "unmatched", created

    try:
        best, _ = await _tmdb_match_with_retry(parsed.title, parsed.year)
        if not best:
            return "unmatched", created

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
        return "matched", created
    except Exception:
        logger.exception("TMDB matching failed for historical file %s", filename)
        return "unmatched", created


async def reindex_messages(session: AsyncSession, messages) -> ReindexResult:
    result = ReindexResult()
    async for message in messages:
        if await index_controller.wait_if_paused():
            break

        result.scanned += 1
        index_controller.progress.scanned = result.scanned
        document = getattr(message, "document", None)
        video = getattr(message, "video", None)
        media = document or video
        if media is None:
            continue

        result.files += 1
        index_controller.progress.files = result.files
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
            index_controller.progress.failed = result.failed
            logger.exception("Historical file indexing failed for message %s", getattr(message, "id", "?"))

        index_controller.progress.created = result.created
        index_controller.progress.existing = result.existing
        index_controller.progress.matched = result.matched
        index_controller.progress.unmatched = result.unmatched

    return result
