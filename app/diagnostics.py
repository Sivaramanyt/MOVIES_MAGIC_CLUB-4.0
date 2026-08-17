from sqlalchemy import text

from app.database.session import engine

REQUIRED_TABLES = {
    "movies",
    "movie_aliases",
    "movie_files",
    "users",
    "groups",
    "settings",
}


async def get_database_diagnostics() -> dict:
    """Return safe schema diagnostics without exposing credentials or row data."""
    async with engine.connect() as connection:
        revision_result = await connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        )
        revision = revision_result.scalar_one_or_none()

        table_result = await connection.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
        )
        tables = {row[0] for row in table_result}

    missing = sorted(REQUIRED_TABLES - tables)

    return {
        "connected": True,
        "migration_revision": revision,
        "required_tables": len(REQUIRED_TABLES),
        "found_tables": len(REQUIRED_TABLES) - len(missing),
        "schema_ready": not missing,
        "missing_tables": missing,
    }
