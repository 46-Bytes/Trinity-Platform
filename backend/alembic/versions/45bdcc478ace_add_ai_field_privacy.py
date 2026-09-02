"""add_ai_field_privacy

Revision ID: 45bdcc478ace
Revises: partial_email_idx
Create Date: 2026-06-30 16:46:43.872648

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '45bdcc478ace'
down_revision = 'partial_email_idx'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_field_privacy',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('questionnaire_type', sa.String(length=50), nullable=False,
                  comment='sale_ready | value_builder'),
        sa.Column('field_name', sa.String(length=255), nullable=False,
                  comment="Matches the 'name' key in the questionnaire JSON"),
        sa.Column('include_in_ai', sa.Boolean(), nullable=False,
                  comment='True = send to Claude; False = strip from AI payload'),
        sa.Column('updated_by_user_id', sa.UUID(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'),
                  nullable=False),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('id'),
        sa.UniqueConstraint('questionnaire_type', 'field_name',
                            name='uq_ai_field_privacy_type_field'),
    )
    op.create_index('ix_ai_field_privacy_questionnaire_type', 'ai_field_privacy',
                    ['questionnaire_type'], unique=False)
    op.create_index('ix_ai_field_privacy_updated_by_user_id', 'ai_field_privacy',
                    ['updated_by_user_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ai_field_privacy_updated_by_user_id', table_name='ai_field_privacy')
    op.drop_index('ix_ai_field_privacy_questionnaire_type', table_name='ai_field_privacy')
    op.drop_table('ai_field_privacy')
