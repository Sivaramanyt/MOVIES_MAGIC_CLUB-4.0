import re
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Movie, MovieAlias


def normalize_movie_title(title: str) -> str:
    """Create a conservative database search/grouping key from a parsed title."""
    value = (title or "").casefold().strip()
    value = re.sub(r"[._\-]+", " ", value)
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


class MovieRepository:
    """Database access for TMDB-backed and database-first movie groups."""

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

    async def get_local_group(self, title: str, year: int | None = None) -> Movie | None:
        normalized = normalize_movie_title(title)
        if not normalized:
            return None
        query = select(Movie).where(
            Movie.tmdb_id.is_(None),
            Movie.normalized_title == normalized,
        )
        if year is None:
            query = query.where(Movie.year.is_(None))
        else:
            query = query.where(Movie.year == year)
        result = await self.session.execute(query.limit(1))
        return result.scalar_one_or_none()

    async def get_or_create_local_group(self, title: str, year: int | None = None) -> tuple[Movie, bool]:
        normalized = normalize_movie_title(title)
        if not normalized:
            raise ValueError("A non-empty title is required for a local movie group")

        existing = await self.get_local_group(title, year)
        if existing is not None:
            return existing, False

        year_key = str(year) if year is not None else "unknown"
        movie = Movie(
            tmdb_id=None,
            title=title.strip(),
            original_title=title.strip(),
            normalized_title=normalized,
            group_key=f"local:{normalized}:{year_key}",
            year=year,
        )
        self.session.add(movie)
        await self.session.flush()
        return movie, True

    async def find_by_title(self, title: str) -> Sequence[Movie]:
        normalized = normalize_movie_title(title)
        if not normalized:
            return []

        pattern = f"%{normalized}%"
        result = await self.session.execute(
            select(Movie)
            .options(selectinload(Movie.aliases), selectinload(Movie.files))
            .where(
                or_(
                    Movie.normalized_title.ilike(pattern),
                    Movie.title.ilike(f"%{title.strip()}%"),
                    Movie.original_title.ilike(f"%{title.strip()}%"),
                    Movie.id.in_(
                        select(MovieAlias.movie_id).where(MovieAlias.alias.ilike(f"%{title.strip()}%"))
                    ),
                )
            )
            .order_by(Movie.year.desc().nullslast(), Movie.title.asc())
        )
        return result.scalars().unique().all()

    async def create(
        self,
        *,
        tmdb_id: int | None,
        title: str,
        original_title: str | None = None,
        normalized_title: str | None = None,
        group_key: str | None = None,
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
            normalized_title=normalized_title or normalize_movie_title(title),
            group_key=group_key or (f"tmdb:{tmdb_id}" if tmdb_id is not None else None),
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

        # Promote an exact database-first group instead of creating a duplicate
        # group when TMDB eventually identifies it.
        local = await self.get_local_group(title, year)
        if local is not None:
            local.tmdb_id = tmdb_id
            local.title = title
            local.original_title = original_title
            local.normalized_title = normalize_movie_title(title)
            local.group_key = f"tmdb:{tmdb_id}"
            local.release_date = release_date
            local.year = year
            local.overview = overview
            local.poster_url = poster_url
            local.backdrop_url = backdrop_url
            local.rating = rating
            await self.session.flush()
            return local, False

        movie = await self.create(
            tmdb_id=tmdb_id,
            title=title,
            original_title=original_title,
            normalized_title=normalize_movie_title(title),
            group_key=f"tmdb:{tmdb_id}",
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
