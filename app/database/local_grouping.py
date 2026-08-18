from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MovieFile
from app.database.repositories.movie_file_repository import MovieFileRepository
from app.database.repositories.movie_repository import MovieRepository
from app.parser.filename_parser import parse_filename


@dataclass
class LocalGroupingResult:
    processed: int = 0
    grouped: int = 0
    new_groups: int = 0
    existing_groups: int = 0
    skipped: int = 0


async def group_unmatched_files(session: AsyncSession, limit: int) -> LocalGroupingResult:
    """Attach unmatched files to exact local title/year groups.

    This never calls TMDB and never changes channel/message identity. It only
    creates/reuses a local Movie row where tmdb_id is NULL.
    """
    result = LocalGroupingResult()
    rows = (
        await session.scalars(
            select(MovieFile)
            .where(MovieFile.movie_id.is_(None))
            .order_by(MovieFile.id.asc())
            .limit(limit)
        )
    ).all()

    movie_repository = MovieRepository(session)
    file_repository = MovieFileRepository(session)

    for row in rows:
        result.processed += 1
        parsed = parse_filename(row.filename)
        await file_repository.update_parsed_metadata(row, parsed)
        if not parsed.title:
            result.skipped += 1
            continue

        movie, created = await movie_repository.get_or_create_local_group(parsed.title, parsed.year)
        await file_repository.attach_movie(row, movie)
        await movie_repository.add_alias(movie, parsed.title)
        result.grouped += 1
        if created:
            result.new_groups += 1
        else:
            result.existing_groups += 1

    await session.commit()
    return result
