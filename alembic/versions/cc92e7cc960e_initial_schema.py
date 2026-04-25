"""initial schema

Revision ID: cc92e7cc960e
Revises: 
Create Date: 2026-04-25 05:42:08.008344

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc92e7cc960e'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the listing table from scratch (initial migration on a fresh database)
    op.create_table(
        'listing',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inquiry_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.VARCHAR(length=7), nullable=False),
        sa.Column('source_url', sa.String(), nullable=False),
        sa.Column('vin', sa.String(), nullable=False, server_default=''),
        sa.Column('title', sa.String(), nullable=False, server_default=''),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('make', sa.String(), nullable=False, server_default=''),
        sa.Column('model', sa.String(), nullable=False, server_default=''),
        sa.Column('mileage', sa.Integer(), nullable=True),
        sa.Column('damage_primary', sa.String(), nullable=False, server_default=''),
        sa.Column('damage_secondary', sa.String(), nullable=False, server_default=''),
        sa.Column('location', sa.String(), nullable=False, server_default=''),
        sa.Column('auction_date', sa.String(), nullable=False, server_default=''),
        sa.Column('current_bid_usd', sa.Float(), nullable=True),
        sa.Column('buy_now_usd', sa.Float(), nullable=True),
        sa.Column('photos_json', sa.String(), nullable=False, server_default='[]'),
        sa.Column('scraped_at', sa.DateTime(), nullable=False),
        sa.Column('ai_repair_estimate_usd_low', sa.Float(), nullable=True),
        sa.Column('ai_repair_estimate_usd_high', sa.Float(), nullable=True),
        sa.Column('ai_damage_score', sa.Integer(), nullable=True),
        sa.Column('ai_notes', sa.String(), nullable=False, server_default=''),
        sa.Column('ai_raw_json', sa.String(), nullable=False, server_default=''),
        sa.Column('total_cost_pln', sa.Float(), nullable=True),
        sa.Column('recommended_rank', sa.Integer(), nullable=True),
        sa.Column('excluded', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['inquiry_id'], ['inquiry.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_listing_inquiry_id'), 'listing', ['inquiry_id'], unique=False)

    # Alter the source column from VARCHAR to the Enum type
    op.alter_column('listing', 'source',
               existing_type=sa.VARCHAR(length=7),
               type_=sa.Enum('copart', 'iaai', 'amerpol', 'auctiongate', 'manual', name='source'),
               existing_nullable=False)


def downgrade() -> None:
    # Revert the source column from Enum back to VARCHAR
    op.alter_column('listing', 'source',
               existing_type=sa.Enum('copart', 'iaai', 'amerpol', 'auctiongate', 'manual', name='source'),
               type_=sa.VARCHAR(length=7),
               existing_nullable=False)

    # Drop the listing table
    op.drop_index(op.f('ix_listing_inquiry_id'), table_name='listing')
    op.drop_table('listing')
