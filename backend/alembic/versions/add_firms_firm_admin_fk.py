"""add the missing firms.firm_admin_id foreign key

Revision ID: add_firms_firm_admin_fk
Revises: 0cfcd28150eb
Create Date: 2026-08-31

Firm.firm_admin_id is declared on the model as
ForeignKey("users.id", ondelete="RESTRICT", use_alter=True) but the constraint
is missing from databases that already had a `firms` table when
create_firms_and_subscriptions_tables ran. That migration only declares the
foreign key inside its `if 'firms' not in tables` branch; the `else` branch
creates an index and nothing else, so a cloned or pre-existing database never
received it. Fresh installs have it, which is why models and database disagree
only on some environments.

This adds the constraint where it is absent, matching the original definition
(RESTRICT on delete) and the naming Postgres would have generated
(firms_firm_admin_id_fkey, alongside the existing firms_subscription_id_fkey).

Guarded, so it is a no-op wherever the constraint already exists. Rows are
verified first: adding the constraint fails loudly if any firm points at a
user that does not exist, rather than being silently skipped.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_firms_firm_admin_fk'
down_revision = '0cfcd28150eb'
branch_labels = None
depends_on = None

_TABLE = 'firms'
_COLUMN = 'firm_admin_id'
_REFERRED = 'users'
_NAME = 'firms_firm_admin_id_fkey'


def _has_fk(inspector, table: str, column: str) -> bool:
    """True if any foreign key on `table` already covers `column`."""
    if table not in inspector.get_table_names():
        return False
    return any(
        column in fk.get('constrained_columns', [])
        for fk in inspector.get_foreign_keys(table)
    )


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if _TABLE not in inspector.get_table_names():
        return
    if _has_fk(inspector, _TABLE, _COLUMN):
        return

    orphans = conn.execute(
        sa.text(
            f"SELECT count(*) FROM {_TABLE} f "
            f"LEFT JOIN {_REFERRED} u ON u.id = f.{_COLUMN} "
            f"WHERE f.{_COLUMN} IS NOT NULL AND u.id IS NULL"
        )
    ).scalar()
    if orphans:
        raise RuntimeError(
            f"Cannot add {_NAME}: {orphans} row(s) in {_TABLE} reference a "
            f"{_REFERRED} row that does not exist. Repair the data first."
        )

    op.create_foreign_key(
        _NAME, _TABLE, _REFERRED, [_COLUMN], ['id'], ondelete='RESTRICT'
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if _has_fk(inspector, _TABLE, _COLUMN):
        op.drop_constraint(_NAME, _TABLE, type_='foreignkey')
