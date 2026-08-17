"""Persist Phase 4.1 parsed filename metadata.

Revision ID: 0003_phase4_1_parsed_metadata
Revises: 0002_phase3_file_intake
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_phase4_1_parsed_metadata"
down_revision = "0002_phase3_file_intake"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movie_files", sa.Column("parsed_title", sa.String(length=500), nullable=True))
    op.add_column("movie_files", sa.Column("parsed_year", sa.Integer(), nullable=True))
    op.add_column("movie_files", sa.Column("source", sa.String(length=50), nullable=True))
    op.add_column("movie_files", sa.Column("codec", sa.String(length=50), nullable=True))
    op.add_column("movie_files", sa.Column("audio", sa.String(length=50), nullable=True))
    op.add_column("movie_files", sa.Column("extension", sa.String(length=20), nullable=True))

    op.create_index("ix_movie_files_parsed_title", "movie_files", ["parsed_title"])
    op.create_index("ix_movie_files_parsed_year", "movie_files", ["parsed_year"])
    op.create_index("ix_movie_files_source", "movie_files", ["source"])


def downgrade() -> None:
    op.drop_index("ix_movie_files_source", table_name="movie_files")
    op.drop_index("ix_movie_files_parsed_year", table_name="movie_files")
    op.drop_index("ix_movie_files_parsed_title", table_name="movie_files")
    op.drop_column("movie_files", "extension")
    op.drop_column("movie_files", "audio")
    op.drop_column("movie_files", "codec")
    op.drop_column("movie_files", "source")
    op.drop_column("movie_files", "parsed_year")
    op.drop_column("movie_files", "parsed_title")
