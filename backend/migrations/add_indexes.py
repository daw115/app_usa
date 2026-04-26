"""
Migration script to add database indexes for performance optimization.
Run this once to add indexes to existing database.
"""
import sqlite3
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import config

def add_indexes():
    db_path = config.database_url.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("Adding indexes to database...")

    # Inquiry indexes
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_inquiry_email ON inquiry(client_email)",
        "CREATE INDEX IF NOT EXISTS idx_inquiry_make ON inquiry(make)",
        "CREATE INDEX IF NOT EXISTS idx_inquiry_model ON inquiry(model)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_inquiry_tracking_token ON inquiry(tracking_token)",

        # Listing indexes
        "CREATE INDEX IF NOT EXISTS idx_listing_source ON listing(source)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_listing_source_url ON listing(source_url)",
        "CREATE INDEX IF NOT EXISTS idx_listing_vin ON listing(vin)",
        "CREATE INDEX IF NOT EXISTS idx_listing_year ON listing(year)",
        "CREATE INDEX IF NOT EXISTS idx_listing_make ON listing(make)",
        "CREATE INDEX IF NOT EXISTS idx_listing_model ON listing(model)",
        "CREATE INDEX IF NOT EXISTS idx_listing_scraped_at ON listing(scraped_at)",
        "CREATE INDEX IF NOT EXISTS idx_listing_damage_score ON listing(ai_damage_score)",
        "CREATE INDEX IF NOT EXISTS idx_listing_total_cost ON listing(total_cost_pln)",
        "CREATE INDEX IF NOT EXISTS idx_listing_excluded ON listing(excluded)",

        # Report indexes
        "CREATE INDEX IF NOT EXISTS idx_report_status ON report(status)",
        "CREATE INDEX IF NOT EXISTS idx_report_created_at ON report(created_at)",
    ]

    for idx_sql in indexes:
        try:
            cursor.execute(idx_sql)
            print(f"✓ {idx_sql.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"✗ Failed: {e}")

    conn.commit()
    conn.close()
    print("\nIndexes added successfully!")

if __name__ == "__main__":
    add_indexes()
