"""add_firm_id_to_users

Revision ID: 67fb5521ba93
Revises: 32ee0bfb8c0d
Create Date: 2026-01-05 17:42:24.176354

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '67fb5521ba93'
down_revision = '32ee0bfb8c0d'
branch_labels = None
depends_on = None


def upgrade() -> None:
       from sqlalchemy import inspect
       from sqlalchemy.dialects import postgresql
       conn = op.get_bind()
       inspector = inspect(conn)
       
       columns = [col['name'] for col in inspector.get_columns('users')]
       if 'firm_id' not in columns:
           op.add_column('users', 
               sa.Column('firm_id', 
                   postgresql.UUID(as_uuid=True), 
                   sa.ForeignKey('firms.id', ondelete='SET NULL'),
                   nullable=True,
                   index=True
               )
           )


def downgrade() -> None:
    pass



