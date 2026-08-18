"""Add database-first local movie groups that do not require TMDB.

Revision ID: 0004_database_first_movie_groups
Revises: 0003_phase4_1_parsed_metadata
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_database_first_movie_groups"
down_revision = "0003_phase4_1_parsed_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("movies", "tmdb_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("movies", sa.Column("normalized_title", sa.String(length=500), nullable=True))
    op.add_column("movies", sa.Column("group_key", sa.String(length=1000), nullable=True))

    op.create_index("ix_movies_normalized_title", "movies", ["normalized_title"])
    op.create_index("ix_movies_group_key", "movies", ["group_key"], unique=True)

    # Existing groups are TMDB-backed. Give them stable normalized/search keys
    # without changing their identity or any linked MovieFile rows.
    op.execute(
        "UPDATE movies "
        "SET normalized_title = lower(trim(title)), "
        "group_key = 'tmdb:' || tmdb_id::text "
        "WHERE tmdb_id IS NOT NULL"
    )


def downgrade() -> None:
    # Refuse a destructive downgrade if local groups exist.
    bind = op.get_bind()
    local_count = bind.execute(sa.text("SELECT count(*) FROM movies WHERE tmdb_id IS NULL")).scalar_one()
    if local_count:
        raise RuntimeError("Cannot downgrade while database-first local movie groups exist")

    op.drop_index("ix_movies_group_key", table_name="movies")
    op.drop_index("ix_movies_normalized_title", table_name="movies")
    op.drop_column("movies", "group_key")
    op.drop_column("movies", "normalized_title")
    op.alter_column("movies", "tmdb_id", existing_type=sa.Integer(), nullable=False)
