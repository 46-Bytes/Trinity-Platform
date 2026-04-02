"""add strategic_business_plans table

Revision ID: add_sbp_table
Revises: 1902d32c0ce6, add_llm_provider_fields
Create Date: 2026-03-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = 'add_sbp_table'
down_revision = ('1902d32c0ce6', 'add_llm_provider_fields')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'strategic_business_plans',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('engagement_id', UUID(as_uuid=True), sa.ForeignKey('engagements.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('diagnostic_id', UUID(as_uuid=True), sa.ForeignKey('diagnostics.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('diagnostic_context', JSONB, nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),

        # Status & step tracking
        sa.Column('status', sa.String(50), nullable=False, server_default='draft', index=True),
        sa.Column('current_step', sa.Integer, nullable=True),
        sa.Column('max_step_reached', sa.Integer, nullable=True),

        # Step 1: Setup
        sa.Column('client_name', sa.String(255), nullable=True),
        sa.Column('industry', sa.String(255), nullable=True),
        sa.Column('planning_horizon', sa.String(50), nullable=True),
        sa.Column('target_audience', sa.Text, nullable=True),
        sa.Column('additional_context', sa.Text, nullable=True),

        # Step 1: Files
        sa.Column('file_ids', JSONB, nullable=True),
        sa.Column('file_mappings', JSONB, nullable=True),
        sa.Column('file_tags', JSONB, nullable=True),
        sa.Column('stored_files', JSONB, nullable=True),

        # Step 2: Cross-Analysis
        sa.Column('cross_analysis', JSONB, nullable=True),
        sa.Column('cross_analysis_advisor_notes', sa.Text, nullable=True),

        # Step 3: Section Drafting
        sa.Column('sections', JSONB, nullable=True),
        sa.Column('current_section_index', sa.Integer, nullable=True),
        sa.Column('emerging_themes', JSONB, nullable=True),

        # Step 4: Final Plan
        sa.Column('final_plan', JSONB, nullable=True),

        # Step 5: Export
        sa.Column('report_version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('generated_report_path', sa.Text, nullable=True),
        sa.Column('employee_variant_requested', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('generated_employee_report_path', sa.Text, nullable=True),

        # Step 6: Presentation
        sa.Column('presentation_slides', JSONB, nullable=True),

        # Conversation & AI
        sa.Column('conversation_history', JSONB, nullable=True),
        sa.Column('ai_model_used', sa.String(100), nullable=True),
        sa.Column('ai_tokens_used', sa.Integer, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.current_timestamp()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table('strategic_business_plans')
