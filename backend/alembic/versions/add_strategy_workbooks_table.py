"""add strategy workbooks table

Revision ID: add_strategy_workbooks
Revises: a8d3b2d2caf9
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_strategy_workbooks'
down_revision = 'a8d3b2d2caf9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Check if table already exists (for cases where table was created manually)
    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    
    if 'strategy_workbooks' not in tables:
        # Create strategy_workbooks table
        op.create_table('strategy_workbooks',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('status', sa.String(length=50), server_default='draft', nullable=False, comment='draft, extracting, ready, failed'),
            sa.Column('uploaded_media_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=True, comment='Array of Media IDs for uploaded documents'),
            sa.Column('template_path', sa.Text(), nullable=True, comment='Path to the template file used'),
            sa.Column('generated_workbook_path', sa.Text(), nullable=True, comment='Path to the generated workbook file'),
            sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True, comment='Structured extracted content from documents'),
            sa.Column('notes', sa.Text(), nullable=True, comment='User notes or review comments'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
            sa.Column('completed_at', sa.DateTime(), nullable=True, comment='When workbook generation completed'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('id')
        )
    
    # Create index if table exists and index doesn't
    if 'strategy_workbooks' in tables:
        indexes = [idx['name'] for idx in inspector.get_indexes('strategy_workbooks')]
        if 'ix_strategy_workbooks_status' not in indexes:
            op.create_index(op.f('ix_strategy_workbooks_status'), 'strategy_workbooks', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_strategy_workbooks_status'), table_name='strategy_workbooks')
    
    # Drop table
    op.drop_table('strategy_workbooks')

