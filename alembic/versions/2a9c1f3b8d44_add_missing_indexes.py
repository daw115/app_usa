"""add missing indexes and unique constraints

Revision ID: 2a9c1f3b8d44
Revises: 395befaef905
Create Date: 2026-04-25 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2a9c1f3b8d44"
down_revision: Union[str, None] = "395befaef905"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Each entry: (index_name, table, columns, unique)
INDEXES = [
    ("ix_inquiry_client_email", "inquiry", ["client_email"], False),
    ("ix_inquiry_make", "inquiry", ["make"], False),
    ("ix_inquiry_model", "inquiry", ["model"], False),
    ("ix_listing_source", "listing", ["source"], False),
    ("ix_listing_source_url", "listing", ["source_url"], True),
    ("ix_listing_vin", "listing", ["vin"], False),
    ("ix_listing_year", "listing", ["year"], False),
    ("ix_listing_make", "listing", ["make"], False),
    ("ix_listing_model", "listing", ["model"], False),
    ("ix_listing_scraped_at", "listing", ["scraped_at"], False),
    ("ix_listing_ai_damage_score", "listing", ["ai_damage_score"], False),
    ("ix_listing_total_cost_pln", "listing", ["total_cost_pln"], False),
    ("ix_listing_excluded", "listing", ["excluded"], False),
    ("ix_report_status", "report", ["status"], False),
    ("ix_report_created_at", "report", ["created_at"], False),
]


def upgrade() -> None:
    # Promote ix_inquiry_tracking_token to UNIQUE (drop + recreate)
    conn = op.get_bind()
    dialect = conn.dialect.name

    if dialect == "postgresql":
        conn.execute(sa.text("DROP INDEX IF EXISTS ix_inquiry_tracking_token"))
        conn.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_inquiry_tracking_token "
            "ON inquiry (tracking_token)"
        ))
    else:
        # SQLite: just create unique index if missing (initial migration is PG-only,
        # so on SQLite the table is built via SQLModel.create_all instead)
        conn.execute(sa.text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_inquiry_tracking_token "
            "ON inquiry (tracking_token)"
        ))

    for name, table, cols, unique in INDEXES:
        if dialect == "postgresql":
            unique_sql = "UNIQUE " if unique else ""
            cols_sql = ", ".join(cols)
            conn.execute(sa.text(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS {name} ON {table} ({cols_sql})"
            ))
        else:
            unique_sql = "UNIQUE " if unique else ""
            cols_sql = ", ".join(cols)
            conn.execute(sa.text(
                f"CREATE {unique_sql}INDEX IF NOT EXISTS {name} ON {table} ({cols_sql})"
            ))


def downgrade() -> None:
    conn = op.get_bind()
    for name, _, _, _ in INDEXES:
        conn.execute(sa.text(f"DROP INDEX IF EXISTS {name}"))
    # Don't drop ix_inquiry_tracking_token — initial migration recreates it
