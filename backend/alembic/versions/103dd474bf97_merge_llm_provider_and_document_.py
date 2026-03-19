"""merge llm_provider and document_templates heads

Revision ID: 103dd474bf97
Revises: add_document_templates, 9267fb9f2c3b
Create Date: 2026-03-19 16:30:37.563417

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '103dd474bf97'
down_revision = ('add_document_templates', '9267fb9f2c3b')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass



