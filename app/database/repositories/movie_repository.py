from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Movie, MovieAlias


class MovieRepository:
    """Database access for movie groups and their aliases.

    This layer deliberately contains no Telegram or TMDB logic. It only reads and
    writes movie-domain records, keeping the grouping engine independent from
    transport and external APIs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, movie_id: int) -> Movie | None:
        result = await self.session.execute(
            select(Movie)
            .options(selectinload(Movie.aliases), selectinload(Movie.files))
            .where(Movie.id == movie_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tmdb_id(self, tmdb_id: int) -> Movie | None:
        result = await self.session.execute(
            select(Movie)
            .options(selectinload(Movie.aliases), selectinload(Movie.files))
            .where(Movie.tmdb_id == tmdb_id)
        )
        return result.scalar_one_or_none()

    async def find_by_title(self, title: str) -> Sequence[Movie]:
        normalized = title.strip()
        if not normalized:
            return []

        pattern = f"%{normalized}%"
        result = await self.session.execute(
            select(Movie)
            .options(selectinload(Movie.aliases))
            .where(
                or_(
                    Movie.title.ilike(pattern),
                    Movie.original_title.ilike(pattern),
                    Movie.id.in_(
                        select(MovieAlias.movie_id).where(MovieAlias.alias.ilike(pattern))
                    ),
                )
            )
            .order_by(Movie.year.desc().nullslast(), Movie.title.asc())
        )
        return result.scalars().unique().all()

    async def create(
        self,
        *,
        tmdb_id: int,
        title: str,
        original_title: str | None = None,
        release_date: str | None = None,
        year: int | None = None,
        overview: str | None = None,
        poster_url: str | None = None,
        backdrop_url: str | None = None,
        rating: float | None = None,
    ) -> Movie:
        movie = Movie(
            tmdb_id=tmdb_id,
            title=title,
            original_title=original_title,
            release_date=release_date,
            year=year,
            overview=overview,
            poster_url=poster_url,
            backdrop_url=backdrop_url,
            rating=rating,
        )
        self.session.add(movie)
        await self.session.flush()
        return movie

    async def get_or_create_by_tmdb(
        self,
        *,
        tmdb_id: int,
        title: str,
        original_title: str | None = None,
        release_date: str | None = None,
        year: int | None = None,
        overview: str | None = None,
        poster_url: str | None = None,
        backdrop_url: str | None = None,
        rating: float | None = None,
    ) -> tuple[Movie, bool]:
        movie = await self.get_by_tmdb_id(tmdb_id)
        if movie is not None:
            return movie, False

        movie = await self.create(
            tmdb_id=tmdb_id,
            title=title,
            original_title=original_title,
            release_date=release_date,
            year=year,
            overview=overview,
            poster_url=poster_url,
            backdrop_url=backdrop_url,
            rating=rating,
        )
        return movie, True

    async def add_alias(self, movie: Movie, alias: str) -> MovieAlias:
        cleaned = alias.strip()
        if not cleaned:
            raise ValueError("Movie alias cannot be empty")

        existing = await self.session.execute(
            select(MovieAlias).where(
                MovieAlias.movie_id == movie.id,
                MovieAlias.alias == cleaned,
            )
        )
        alias_row = existing.scalar_one_or_none()
        if alias_row is not None:
            return alias_row

        alias_row = MovieAlias(movie_id=movie.id, alias=cleaned)
        self.session.add(alias_row)
        await self.session.flush()
        return alias_row
