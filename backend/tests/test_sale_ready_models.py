"""
Sale Ready model mapping. No database: these read the SQLAlchemy mappers only.

Task has two things called "notes". Task.notes is the relationship to Note
records; the Sale Ready per-task text lives in the tasks.notes column, mapped
as Task.task_notes. Renaming either would silently replace the other.
"""
from sqlalchemy import inspect

from app.models import (
    EngagementDDItem,
    EngagementStageState,
    Note,
    ProgramDDTemplate,
    ProgramStage,
    ProgramTaskTemplate,
    Task,
)


class TestTaskNotesMapping:

    def test_notes_is_still_the_note_relationship(self):
        mapper = inspect(Task)
        assert "notes" in mapper.relationships
        assert mapper.relationships["notes"].mapper.class_ is Note

    def test_task_notes_maps_the_notes_column(self):
        assert inspect(Task).columns["task_notes"].name == "notes"

    def test_sale_ready_task_columns(self):
        columns = inspect(Task).columns
        assert "section" in columns
        fks = {fk.target_fullname for fk in columns["source_task_template_id"].foreign_keys}
        assert fks == {"program_task_template.id"}


def test_stage_ui_config_none_is_stored_as_sql_null(db_session):
    """
    ui_config None must be SQL NULL, not the JSON value 'null' - otherwise
    `ui_config IS NULL` misses stages with no config. Uses its own program
    type so seeded data cannot affect the result; rolled back after.
    """
    from sqlalchemy import text

    db_session.add(ProgramStage(program_type="test_none_as_null", stage_code="X", stage_type="module",
                                default_order=1, title="t", ui_config=None))
    db_session.flush()
    stored = db_session.execute(text(
        "SELECT ui_config IS NULL FROM program_stage WHERE program_type = 'test_none_as_null'"
    )).scalar()
    assert stored is True


def test_sale_ready_models_map_their_tables():
    assert {m.__tablename__ for m in (ProgramStage, ProgramTaskTemplate, ProgramDDTemplate,
                                      EngagementStageState, EngagementDDItem)} == {
        "program_stage", "program_task_template", "program_dd_template",
        "engagement_stage_state", "engagement_dd_item",
    }
