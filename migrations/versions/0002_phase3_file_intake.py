"""Allow Phase 3 Telegram files to exist before movie grouping.

Revision ID: 0002_phase3_file_intake
Revises: 0001_initial_schema
"""
from alembic import op

revision = "0002_phase3_file_intake"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("movie_files", "movie_id", nullable=True)


def downgrade() -> None:
    op.alter_column("movie_files", "movie_id", nullable=False)
