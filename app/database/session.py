import logging
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize_database_url(url: str) -> str:
    """Normalize provider PostgreSQL URLs for SQLAlchemy's asyncpg driver."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    parts = urlsplit(url)
    if parts.scheme == "postgresql":
        parts = parts._replace(scheme="postgresql+asyncpg")

    # Neon connection strings may contain channel_binding=require.
    # asyncpg does not recognize this as a connection option, so it can
    # otherwise be forwarded as a PostgreSQL server setting and fail.
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() != "channel_binding"
    ]

    # Neon requires TLS. Preserve an existing sslmode or add the required one.
    if not any(key.lower() == "sslmode" for key, _ in query):
        query.append(("sslmode", "require"))

    return urlunsplit(parts._replace(query=urlencode(query)))


engine = create_async_engine(
    _normalize_database_url(settings.database_url),
    pool_pre_ping=True,
    connect_args={"timeout": 10},
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _safe_database_error(exc: Exception) -> str:
    if isinstance(exc, OperationalError):
        return "operational_error"
    if isinstance(exc, DBAPIError):
        return "database_driver_error"
    return exc.__class__.__name__.lower()


async def check_database_connection() -> bool:
    """Return True when PostgreSQL accepts a simple connectivity query."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.warning("PostgreSQL health check failed: %s", _safe_database_error(exc))
        return False


async def close_database() -> None:
    await engine.dispose()
