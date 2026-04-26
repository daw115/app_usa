"""initial schema

Revision ID: 395befaef905
Revises:
Create Date: 2026-04-25 08:09:06.333671

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '395befaef905'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _upgrade_postgres(conn) -> None:
    # Create enum types with existence check
    for typname, values in [
        ("source", "'copart', 'iaai', 'amerpol', 'auctiongate', 'manual'"),
        ("damagetolerance", "'none', 'light', 'medium', 'heavy'"),
        ("inquirystatus", "'new', 'searching', 'analyzing', 'ready', 'sent', 'archived'"),
        ("reportstatus", "'draft', 'approved', 'sent'"),
    ]:
        conn.execute(sa.text(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{typname}') THEN
                    CREATE TYPE {typname} AS ENUM ({values});
                END IF;
            END $$;
        """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS inquiry (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            client_name VARCHAR NOT NULL,
            client_email VARCHAR NOT NULL,
            client_phone VARCHAR NOT NULL DEFAULT '',
            make VARCHAR NOT NULL DEFAULT '',
            model VARCHAR NOT NULL DEFAULT '',
            year_from INTEGER,
            year_to INTEGER,
            budget_pln INTEGER,
            mileage_max INTEGER,
            body_type VARCHAR NOT NULL DEFAULT '',
            fuel VARCHAR NOT NULL DEFAULT '',
            transmission VARCHAR NOT NULL DEFAULT '',
            damage_tolerance damagetolerance NOT NULL,
            extra_notes VARCHAR NOT NULL DEFAULT '',
            status inquirystatus NOT NULL,
            tracking_token VARCHAR NOT NULL
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS listing (
            id SERIAL PRIMARY KEY,
            inquiry_id INTEGER NOT NULL REFERENCES inquiry(id),
            source source NOT NULL,
            source_url VARCHAR NOT NULL,
            vin VARCHAR NOT NULL DEFAULT '',
            title VARCHAR NOT NULL DEFAULT '',
            year INTEGER,
            make VARCHAR NOT NULL DEFAULT '',
            model VARCHAR NOT NULL DEFAULT '',
            mileage INTEGER,
            damage_primary VARCHAR NOT NULL DEFAULT '',
            damage_secondary VARCHAR NOT NULL DEFAULT '',
            location VARCHAR NOT NULL DEFAULT '',
            auction_date VARCHAR NOT NULL DEFAULT '',
            current_bid_usd FLOAT,
            buy_now_usd FLOAT,
            photos_json VARCHAR NOT NULL DEFAULT '[]',
            scraped_at TIMESTAMP NOT NULL,
            ai_repair_estimate_usd_low FLOAT,
            ai_repair_estimate_usd_high FLOAT,
            ai_damage_score INTEGER,
            ai_notes VARCHAR NOT NULL DEFAULT '',
            ai_raw_json VARCHAR NOT NULL DEFAULT '',
            total_cost_pln FLOAT,
            recommended_rank INTEGER,
            excluded BOOLEAN NOT NULL DEFAULT FALSE
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS report (
            id SERIAL PRIMARY KEY,
            inquiry_id INTEGER NOT NULL REFERENCES inquiry(id),
            html_body VARCHAR NOT NULL DEFAULT '',
            selected_listing_ids VARCHAR NOT NULL DEFAULT '[]',
            status reportstatus NOT NULL,
            created_at TIMESTAMP NOT NULL,
            sent_at TIMESTAMP,
            gmail_draft_id VARCHAR NOT NULL DEFAULT '',
            subject VARCHAR NOT NULL DEFAULT ''
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            transport_usd FLOAT NOT NULL,
            agent_fee_usd FLOAT NOT NULL,
            customs_pct FLOAT NOT NULL,
            excise_pct FLOAT NOT NULL,
            vat_pct FLOAT NOT NULL,
            margin_pln FLOAT NOT NULL,
            repair_safety_pct FLOAT NOT NULL,
            usd_pln_rate FLOAT NOT NULL,
            auto_usd_rate BOOLEAN NOT NULL,
            auto_search_enabled BOOLEAN NOT NULL
        );
    """))


def _upgrade_sqlite(conn) -> None:
    # SQLite has no enum type — store as VARCHAR with CHECK constraints.
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS inquiry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP NOT NULL,
            client_name VARCHAR NOT NULL,
            client_email VARCHAR NOT NULL,
            client_phone VARCHAR NOT NULL DEFAULT '',
            make VARCHAR NOT NULL DEFAULT '',
            model VARCHAR NOT NULL DEFAULT '',
            year_from INTEGER,
            year_to INTEGER,
            budget_pln INTEGER,
            mileage_max INTEGER,
            body_type VARCHAR NOT NULL DEFAULT '',
            fuel VARCHAR NOT NULL DEFAULT '',
            transmission VARCHAR NOT NULL DEFAULT '',
            damage_tolerance VARCHAR NOT NULL,
            extra_notes VARCHAR NOT NULL DEFAULT '',
            status VARCHAR NOT NULL,
            tracking_token VARCHAR NOT NULL
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS listing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inquiry_id INTEGER NOT NULL REFERENCES inquiry(id),
            source VARCHAR NOT NULL,
            source_url VARCHAR NOT NULL,
            vin VARCHAR NOT NULL DEFAULT '',
            title VARCHAR NOT NULL DEFAULT '',
            year INTEGER,
            make VARCHAR NOT NULL DEFAULT '',
            model VARCHAR NOT NULL DEFAULT '',
            mileage INTEGER,
            damage_primary VARCHAR NOT NULL DEFAULT '',
            damage_secondary VARCHAR NOT NULL DEFAULT '',
            location VARCHAR NOT NULL DEFAULT '',
            auction_date VARCHAR NOT NULL DEFAULT '',
            current_bid_usd FLOAT,
            buy_now_usd FLOAT,
            photos_json VARCHAR NOT NULL DEFAULT '[]',
            scraped_at TIMESTAMP NOT NULL,
            ai_repair_estimate_usd_low FLOAT,
            ai_repair_estimate_usd_high FLOAT,
            ai_damage_score INTEGER,
            ai_notes VARCHAR NOT NULL DEFAULT '',
            ai_raw_json VARCHAR NOT NULL DEFAULT '',
            total_cost_pln FLOAT,
            recommended_rank INTEGER,
            excluded BOOLEAN NOT NULL DEFAULT 0
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS report (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inquiry_id INTEGER NOT NULL REFERENCES inquiry(id),
            html_body VARCHAR NOT NULL DEFAULT '',
            selected_listing_ids VARCHAR NOT NULL DEFAULT '[]',
            status VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            sent_at TIMESTAMP,
            gmail_draft_id VARCHAR NOT NULL DEFAULT '',
            subject VARCHAR NOT NULL DEFAULT ''
        );
    """))

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY DEFAULT 1,
            transport_usd FLOAT NOT NULL,
            agent_fee_usd FLOAT NOT NULL,
            customs_pct FLOAT NOT NULL,
            excise_pct FLOAT NOT NULL,
            vat_pct FLOAT NOT NULL,
            margin_pln FLOAT NOT NULL,
            repair_safety_pct FLOAT NOT NULL,
            usd_pln_rate FLOAT NOT NULL,
            auto_usd_rate BOOLEAN NOT NULL,
            auto_search_enabled BOOLEAN NOT NULL
        );
    """))


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        _upgrade_postgres(conn)
    else:
        _upgrade_sqlite(conn)

    # Indexes (cross-dialect)
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_inquiry_created_at ON inquiry (created_at);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_inquiry_status ON inquiry (status);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_inquiry_tracking_token ON inquiry (tracking_token);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_listing_inquiry_id ON listing (inquiry_id);"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS ix_report_inquiry_id ON report (inquiry_id);"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS settings;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS report;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS listing;"))
    conn.execute(sa.text("DROP TABLE IF EXISTS inquiry;"))
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("DROP TYPE IF EXISTS reportstatus;"))
        conn.execute(sa.text("DROP TYPE IF EXISTS inquirystatus;"))
        conn.execute(sa.text("DROP TYPE IF EXISTS damagetolerance;"))
        conn.execute(sa.text("DROP TYPE IF EXISTS source;"))
