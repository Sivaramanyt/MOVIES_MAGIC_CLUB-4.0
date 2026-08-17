from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Movie


async def get_movie_group(
    session: AsyncSession,
    *,
    title: str,
    year: int | None = None,
) -> Movie | None:
    """Return one movie group with all linked files.

    Group identity is the TMDB-backed Movie row. Files never create a second
    movie group when they point at the same TMDB ID.
    """
    query = (
        select(Movie)
        .options(selectinload(Movie.aliases), selectinload(Movie.files))
        .where(Movie.title.ilike(title.strip()))
    )
    if year is not None:
        query = query.where(Movie.year == year)

    result = await session.execute(query.order_by(Movie.id.asc()).limit(1))
    return result.scalar_one_or_none()


def group_file_count(movie: Movie) -> int:
    """Return the number of Telegram files currently grouped under a movie."""
    return len(movie.files)
