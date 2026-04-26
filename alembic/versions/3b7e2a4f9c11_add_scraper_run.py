"""add scraper_run table

Revision ID: 3b7e2a4f9c11
Revises: 2a9c1f3b8d44
Create Date: 2026-04-25 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3b7e2a4f9c11"
down_revision: Union[str, None] = "2a9c1f3b8d44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        # `source` enum already created by initial migration
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS scraper_run (
                id SERIAL PRIMARY KEY,
                source source NOT NULL,
                started_at TIMESTAMP NOT NULL,
                inquiry_id INTEGER REFERENCES inquiry(id),
                success BOOLEAN NOT NULL DEFAULT TRUE,
                error VARCHAR NOT NULL DEFAULT '',
                results_count INTEGER NOT NULL DEFAULT 0
            );
        """))
    else:
        conn.execute(sa.text("""
            CREATE TABLE IF NOT EXISTS scraper_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source VARCHAR NOT NULL,
                started_at TIMESTAMP NOT NULL,
                inquiry_id INTEGER REFERENCES inquiry(id),
                success BOOLEAN NOT NULL DEFAULT 1,
                error VARCHAR NOT NULL DEFAULT '',
                results_count INTEGER NOT NULL DEFAULT 0
            );
        """))

    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_scraper_run_source ON scraper_run (source)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_scraper_run_started_at ON scraper_run (started_at)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_scraper_run_inquiry_id ON scraper_run (inquiry_id)"
    ))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS scraper_run"))
