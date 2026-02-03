"""Add BBA report generation columns

Revision ID: add_bba_report_columns
Revises: remove_unique_sub_id
Create Date: 2026-01-29

Adds columns for Steps 6-7 of the BBA report builder workflow:
- twelve_month_plan: JSONB for detailed recommendations
- plan_notes: Text for plan disclaimer
- executive_summary: Text for executive summary
- final_report: JSONB for complete compiled report
- report_version: Integer for versioning
- conversation_history: JSONB for AI conversation context
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = 'add_bba_report_columns'
down_revision = 'remove_unique_sub_id'
branch_labels = None
depends_on = None


def upgrade():
    # Get connection for checking existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if bba table exists
    tables = inspector.get_table_names()
    if 'bba' not in tables:
        # Table doesn't exist, skip migration
        return
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('bba')]
    
    # Add twelve_month_plan column if it doesn't exist
    if 'twelve_month_plan' not in columns:
        op.add_column('bba', sa.Column(
            'twelve_month_plan',
            JSONB,
            nullable=True,
            comment='Detailed recommendations with Purpose, Objectives, Actions, BBA Support, Outcomes'
        ))
    
    # Add plan_notes column if it doesn't exist
    if 'plan_notes' not in columns:
        op.add_column('bba', sa.Column(
            'plan_notes',
            sa.Text(),
            nullable=True,
            comment='Notes/disclaimer for the 12-month plan'
        ))
    
    # Add executive_summary column if it doesn't exist
    if 'executive_summary' not in columns:
        op.add_column('bba', sa.Column(
            'executive_summary',
            sa.Text(),
            nullable=True,
            comment='2-4 paragraph executive summary'
        ))
    
    # Add final_report column if it doesn't exist
    if 'final_report' not in columns:
        op.add_column('bba', sa.Column(
            'final_report',
            JSONB,
            nullable=True,
            comment='Complete compiled report data'
        ))
    
    # Add report_version column if it doesn't exist
    if 'report_version' not in columns:
        op.add_column('bba', sa.Column(
            'report_version',
            sa.Integer(),
            nullable=False,
            server_default='1',
            comment='Report version number'
        ))
    
    # Add conversation_history column if it doesn't exist
    if 'conversation_history' not in columns:
        op.add_column('bba', sa.Column(
            'conversation_history',
            JSONB,
            nullable=True,
            comment='Message history for AI conversation context'
        ))


def downgrade():
    # Get connection for checking existing columns
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if bba table exists
    tables = inspector.get_table_names()
    if 'bba' not in tables:
        return
    
    # Get existing columns
    columns = [col['name'] for col in inspector.get_columns('bba')]
    
    # Remove columns if they exist
    if 'conversation_history' in columns:
        op.drop_column('bba', 'conversation_history')
    
    if 'report_version' in columns:
        op.drop_column('bba', 'report_version')
    
    if 'final_report' in columns:
        op.drop_column('bba', 'final_report')
    
    if 'executive_summary' in columns:
        op.drop_column('bba', 'executive_summary')
    
    if 'plan_notes' in columns:
        op.drop_column('bba', 'plan_notes')
    
    if 'twelve_month_plan' in columns:
        op.drop_column('bba', 'twelve_month_plan')
