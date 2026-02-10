"""Empty migration to satisfy missing revision add_plan_notes_to_bba"""

from alembic import op
import sqlalchemy as sa

revision = 'add_plan_notes_to_bba'
down_revision = 'dd5fedfeefbf'
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass