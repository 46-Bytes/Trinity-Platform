"""merge pd-scorecard branch with main schema cleanup

Revision ID: merge_pd_scorecard_cleanup
Revises: 50f7a483da0a, align_schema_models
Create Date: 2026-08-25

Merge-only revision. Two lineages both descend from 45bdcc478ace:

  45bdcc478ace -+- 5cba10191710 -> 50f7a483da0a          (pd-scorecard feature)
                +- drop_login_security_cols -> align_schema_models   (main cleanup)

The cleanup branch is deliberately parented on 45bdcc478ace so it can ship to
main without pulling in the unmerged feature branch. This revision joins the
two so `upgrade head` resolves to a single target on this branch.

No schema changes - both upgrade() and downgrade() are intentionally empty.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_pd_scorecard_cleanup'
down_revision = ('50f7a483da0a', 'align_schema_models')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
