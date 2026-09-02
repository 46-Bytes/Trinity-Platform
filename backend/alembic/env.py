"""
Alembic environment configuration.
"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from alembic.operations import ops as alembic_ops
import os
import sys

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app.models import User  # Import all models
from app import models
from app.config import settings

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with our DATABASE_URL from settings
config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here for 'autogenerate' support
target_metadata = Base.metadata


# Redundant UNIQUE (id) constraints that duplicate each table's primary key.
# drop_redundant_uniques deliberately left these in place: a foreign key is
# bound to each one's index rather than to the primary key, so dropping them
# would fail or force ~56 foreign keys to be rebuilt. They are real in the
# database and intentionally absent from the models, which autogenerate would
# otherwise report as drift on every run. Exempted here rather than declared on
# the models so a database built from metadata does not inherit the redundancy.
EXEMPT_UNIQUE_CONSTRAINTS = {
    ("conversations", "conversations_id_key"),
    ("diagnostics", "diagnostics_id_key"),
    ("engagements", "engagements_id_key"),
    ("firms", "firms_id_key"),
    ("media", "media_id_key"),
    ("subscriptions", "subscriptions_id_key"),
    ("tasks", "tasks_id_key"),
    ("users", "users_id_key"),
}


def include_object(object_, name, type_, reflected, compare_to) -> bool:
    """Exclude the exempt redundant unique constraints from autogenerate."""
    if type_ == "unique_constraint":
        table_name = getattr(getattr(object_, "table", None), "name", None)
        if (table_name, name) in EXEMPT_UNIQUE_CONSTRAINTS:
            return False
    return True


def _is_comment_only(op) -> bool:
    """True only for ops whose sole change is a table or column comment.

    An AlterColumnOp that also changes type, nullability, server default or
    name is NOT comment-only and must stay visible.
    """
    if isinstance(op, (alembic_ops.CreateTableCommentOp, alembic_ops.DropTableCommentOp)):
        return True
    if isinstance(op, alembic_ops.AlterColumnOp):
        return (
            op.modify_comment is not False
            and op.modify_nullable is None
            and op.modify_server_default is False
            and op.modify_name is None
            and op.modify_type is None
        )
    return False


def strip_comment_directives(_context, _revision, directives) -> None:
    """Drop comment-only diffs so autogenerate and `alembic check` report
    structural drift only. Comments carry no enforcement, and several tables
    were created by guarded migrations that never applied theirs.
    """
    for script in directives:
        for upgrade_ops in script.upgrade_ops_list:
            kept = []
            for op in upgrade_ops.ops:
                if isinstance(op, alembic_ops.ModifyTableOps):
                    op.ops = [o for o in op.ops if not _is_comment_only(o)]
                    if op.ops:
                        kept.append(op)
                elif not _is_comment_only(op):
                    kept.append(op)
            upgrade_ops.ops = kept


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        process_revision_directives=strip_comment_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            process_revision_directives=strip_comment_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()



