import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.repositories.movie_repository import MovieRepository


async def run_movie_repository_smoke_test(session: AsyncSession) -> dict:
    """Create, read, and clean up one isolated temporary movie in a transaction."""
    marker = uuid.uuid4().hex
    # Movie.tmdb_id is a PostgreSQL INTEGER, so keep the diagnostic value
    # safely below the signed 32-bit maximum.
    tmdb_id = 1_000_000_000 + int(marker[:7], 16)
    title = f"__MMC_REPOSITORY_TEST__{marker}"

    repository = MovieRepository(session)

    try:
        movie = await repository.create(
            tmdb_id=tmdb_id,
            title=title,
            original_title=title,
            year=2099,
        )
        await session.flush()
        created_id = movie.id

        read_movie = await repository.get_by_tmdb_id(tmdb_id)
        if read_movie is None or read_movie.id != created_id:
            raise RuntimeError("repository read-back verification failed")

        # Roll back the transaction so no test data survives in production.
        await session.rollback()

        return {
            "success": True,
            "created": True,
            "read_back": True,
            "cleaned_up": True,
        }
    except Exception:
        await session.rollback()
        raise
