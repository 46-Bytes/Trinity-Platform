"""remove unique constraint from subscription_id in firms

Revision ID: remove_unique_sub_id
Revises: merge_all_current_heads
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'remove_unique_sub_id'
down_revision = 'merge_all_current_heads'  # After merging all heads
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove unique constraint from subscription_id in firms table.
    This allows multiple firms to share the same subscription (one-to-many relationship).
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'firms' not in tables:
        return
    
    # Get all indexes on firms table
    indexes = {idx['name']: idx for idx in inspector.get_indexes('firms')}
    
    # Check if the unique index exists
    index_name = 'ix_firms_subscription_id'
    if index_name in indexes:
        # Drop the unique index
        op.drop_index(index_name, table_name='firms')
        
        # Recreate as non-unique index
        op.create_index(index_name, 'firms', ['subscription_id'], unique=False)
    
    # Also check for unique constraint (in case it was created as a constraint instead of index)
    unique_constraints = {uc['name']: uc for uc in inspector.get_unique_constraints('firms')}
    for constraint_name, constraint in unique_constraints.items():
        if 'subscription_id' in constraint['column_names']:
            op.drop_constraint(constraint_name, 'firms', type_='unique')
            # Recreate as non-unique index if not already exists
            if index_name not in {idx['name'] for idx in inspector.get_indexes('firms')}:
                op.create_index(index_name, 'firms', ['subscription_id'], unique=False)


def downgrade() -> None:
    """
    Restore unique constraint on subscription_id (one-to-one relationship).
    """
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'firms' not in tables:
        return
    
    # Get all indexes on firms table
    indexes = {idx['name']: idx for idx in inspector.get_indexes('firms')}
    
    index_name = 'ix_firms_subscription_id'
    if index_name in indexes:
        # Drop the non-unique index
        op.drop_index(index_name, table_name='firms')
        
        # Recreate as unique index
        op.create_index(index_name, 'firms', ['subscription_id'], unique=True)

