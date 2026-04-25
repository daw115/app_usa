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


def upgrade() -> None:
    # Create enum types for PostgreSQL using raw SQL with IF NOT EXISTS
    conn = op.get_bind()
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS source AS ENUM ('copart', 'iaai', 'amerpol', 'auctiongate', 'manual')"))
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS damagetolerance AS ENUM ('none', 'light', 'medium', 'heavy')"))
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS inquirystatus AS ENUM ('new', 'searching', 'analyzing', 'ready', 'sent', 'archived')"))
    conn.execute(sa.text("CREATE TYPE IF NOT EXISTS reportstatus AS ENUM ('draft', 'approved', 'sent')"))

    # Define enum types for table creation
    source_enum = sa.Enum('copart', 'iaai', 'amerpol', 'auctiongate', 'manual', name='source', create_type=False)
    damage_tolerance_enum = sa.Enum('none', 'light', 'medium', 'heavy', name='damagetolerance', create_type=False)
    inquiry_status_enum = sa.Enum('new', 'searching', 'analyzing', 'ready', 'sent', 'archived', name='inquirystatus', create_type=False)
    report_status_enum = sa.Enum('draft', 'approved', 'sent', name='reportstatus', create_type=False)

    # Create inquiry table
    op.create_table(
        'inquiry',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('client_name', sa.String(), nullable=False),
        sa.Column('client_email', sa.String(), nullable=False),
        sa.Column('client_phone', sa.String(), nullable=False),
        sa.Column('make', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('year_from', sa.Integer(), nullable=True),
        sa.Column('year_to', sa.Integer(), nullable=True),
        sa.Column('budget_pln', sa.Integer(), nullable=True),
        sa.Column('mileage_max', sa.Integer(), nullable=True),
        sa.Column('body_type', sa.String(), nullable=False),
        sa.Column('fuel', sa.String(), nullable=False),
        sa.Column('transmission', sa.String(), nullable=False),
        sa.Column('damage_tolerance', damage_tolerance_enum, nullable=False),
        sa.Column('extra_notes', sa.String(), nullable=False),
        sa.Column('status', inquiry_status_enum, nullable=False),
        sa.Column('tracking_token', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inquiry_created_at'), 'inquiry', ['created_at'], unique=False)
    op.create_index(op.f('ix_inquiry_status'), 'inquiry', ['status'], unique=False)
    op.create_index(op.f('ix_inquiry_tracking_token'), 'inquiry', ['tracking_token'], unique=False)

    # Create listing table
    op.create_table(
        'listing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inquiry_id', sa.Integer(), nullable=False),
        sa.Column('source', source_enum, nullable=False),
        sa.Column('source_url', sa.String(), nullable=False),
        sa.Column('vin', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('make', sa.String(), nullable=False),
        sa.Column('model', sa.String(), nullable=False),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('damage_primary', sa.String(), nullable=False),
        sa.Column('damage_secondary', sa.String(), nullable=False),
        sa.Column('location', sa.String(), nullable=False),
        sa.Column('auction_date', sa.String(), nullable=False),
        sa.Column('current_bid_usd', sa.Float(), nullable=True),
        sa.Column('buy_now_usd', sa.Float(), nullable=True),
        sa.Column('photos_json', sa.String(), nullable=False),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.Column('ai_repair_estimate_usd_low', sa.Float(), nullable=True),
        sa.Column('ai_repair_estimate_usd_high', sa.Float(), nullable=True),
        sa.Column('ai_damage_score', sa.Integer(), nullable=True),
        sa.Column('ai_notes', sa.String(), nullable=False),
        sa.Column('ai_raw_json', sa.String(), nullable=False),
        sa.Column('total_cost_pln', sa.Float(), nullable=True),
        sa.Column('recommended_rank', sa.Integer(), nullable=True),
        sa.Column('excluded', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['inquiry_id'], ['inquiry.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_listing_inquiry_id'), 'listing', ['inquiry_id'], unique=False)

    # Create report table
    op.create_table(
        'report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inquiry_id', sa.Integer(), nullable=False),
        sa.Column('html_body', sa.String(), nullable=False),
        sa.Column('selected_listing_ids', sa.String(), nullable=False),
        sa.Column('status', report_status_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('gmail_draft_id', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=False),
        sa.ForeignKeyConstraint(['inquiry_id'], ['inquiry.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_inquiry_id'), 'report', ['inquiry_id'], unique=False)

    # Create settings table
    op.create_table(
        'settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('transport_usd', sa.Float(), nullable=False),
        sa.Column('agent_fee_usd', sa.Float(), nullable=False),
        sa.Column('customs_pct', sa.Float(), nullable=False),
        sa.Column('excise_pct', sa.Float(), nullable=False),
        sa.Column('vat_pct', sa.Float(), nullable=False),
        sa.Column('margin_pln', sa.Float(), nullable=False),
        sa.Column('repair_safety_pct', sa.Float(), nullable=False),
        sa.Column('usd_pln_rate', sa.Float(), nullable=False),
        sa.Column('auto_usd_rate', sa.Boolean(), nullable=False),
        sa.Column('auto_search_enabled', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('settings')
    op.drop_index(op.f('ix_report_inquiry_id'), table_name='report')
    op.drop_table('report')
    op.drop_index(op.f('ix_listing_inquiry_id'), table_name='listing')
    op.drop_table('listing')
    op.drop_index(op.f('ix_inquiry_tracking_token'), table_name='inquiry')
    op.drop_index(op.f('ix_inquiry_status'), table_name='inquiry')
    op.drop_index(op.f('ix_inquiry_created_at'), table_name='inquiry')
    op.drop_table('inquiry')

    # Drop enum types
    sa.Enum(name='reportstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='inquirystatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='damagetolerance').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='source').drop(op.get_bind(), checkfirst=True)
