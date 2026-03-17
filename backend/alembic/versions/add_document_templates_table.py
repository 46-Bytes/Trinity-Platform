"""add document_templates table

Revision ID: add_document_templates
Revises: f227a49caf86
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_document_templates'
down_revision = 'f227a49caf86'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'document_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('file_data', sa.LargeBinary(), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploaded_by_user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_name'),
    )
    op.create_index(op.f('ix_document_templates_file_name'), 'document_templates', ['file_name'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_document_templates_file_name'), table_name='document_templates')
    op.drop_table('document_templates')
