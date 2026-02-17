"""Add client_ids array to engagements

Revision ID: f71d9e32e953
Revises: 4a3c2b1d0e9f
Create Date: 2025-01-XX

This migration adds a client_ids array column to engagements and migrates
existing client_id values to the new array format.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f71d9e32e953'
down_revision = '4a3c2b1d0e9f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add client_ids array column
    op.add_column('engagements', 
        sa.Column('client_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True, 
                  comment='Array of client user IDs'))
    
    # Migrate existing client_id values to client_ids array
    op.execute("""
        UPDATE engagements 
        SET client_ids = ARRAY[client_id]::uuid[]
        WHERE client_id IS NOT NULL AND client_ids IS NULL
    """)
    
    # Make client_id nullable for backward compatibility
    op.alter_column('engagements', 'client_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    # Restore client_id from first element of client_ids array if it exists
    op.execute("""
        UPDATE engagements 
        SET client_id = client_ids[1]
        WHERE client_ids IS NOT NULL AND array_length(client_ids, 1) > 0
    """)
    
    # Make client_id not nullable again
    op.alter_column('engagements', 'client_id',
                    existing_type=postgresql.UUID(as_uuid=True),
                    nullable=False,
                    existing_nullable=True)
    
    # Drop client_ids column
    op.drop_column('engagements', 'client_ids')

