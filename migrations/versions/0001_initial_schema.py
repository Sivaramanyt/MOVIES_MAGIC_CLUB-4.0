"""Initial movie database schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("original_title", sa.String(500)),
        sa.Column("release_date", sa.String(20)),
        sa.Column("year", sa.Integer()),
        sa.Column("overview", sa.Text()),
        sa.Column("poster_url", sa.Text()),
        sa.Column("backdrop_url", sa.Text()),
        sa.Column("rating", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("tmdb_id"),
    )
    op.create_index("ix_movies_tmdb_id", "movies", ["tmdb_id"])
    op.create_index("ix_movies_year", "movies", ["year"])

    op.create_table(
        "movie_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("alias", sa.String(500), nullable=False),
    )
    op.create_index("ix_movie_aliases_alias", "movie_aliases", ["alias"])

    op.create_table(
        "movie_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("movie_id", sa.Integer(), sa.ForeignKey("movies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_file_id", sa.String(500), nullable=False),
        sa.Column("file_unique_id", sa.String(500)),
        sa.Column("filename", sa.String(1000), nullable=False),
        sa.Column("language", sa.String(100)),
        sa.Column("quality", sa.String(50)),
        sa.Column("file_size", sa.BigInteger()),
        sa.Column("mime_type", sa.String(200)),
        sa.Column("indexed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("channel_id", "message_id", name="uq_movie_files_channel_message"),
    )
    op.create_index("ix_movie_files_movie_id", "movie_files", ["movie_id"])
    op.create_index("ix_movie_files_channel_id", "movie_files", ["channel_id"])
    op.create_index("ix_movie_files_language", "movie_files", ["language"])
    op.create_index("ix_movie_files_quality", "movie_files", ["quality"])
    op.create_index("ix_movie_files_movie_language_quality", "movie_files", ["movie_id", "language", "quality"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(255)),
        sa.Column("first_name", sa.String(255)),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("telegram_user_id"),
    )
    op.create_index("ix_users_telegram_user_id", "users", ["telegram_user_id"])

    op.create_table(
        "groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_chat_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("telegram_chat_id"),
    )
    op.create_index("ix_groups_telegram_chat_id", "groups", ["telegram_chat_id"])

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text()),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_settings_key", "settings", ["key"])


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_table("groups")
    op.drop_table("users")
    op.drop_table("movie_files")
    op.drop_table("movie_aliases")
    op.drop_table("movies")
